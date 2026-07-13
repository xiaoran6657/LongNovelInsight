"""Deterministic cross-work global entity registry builder.

No LLM calls — merges extracted atoms across Works using stable IDs,
canonical names, aliases, and normalized string matching.
"""

import json
import re

from sqlmodel import Session, select

from models.chunk import Chunk
from models.document import Document
from models.entity_mention import EntityMention
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.global_entity import GlobalEntity
from models.graph_snapshot import GraphSnapshot


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase ASCII, strip punctuation/whitespace.

    Chinese characters are kept intact.
    """
    name = name.strip()
    # Normalize full-width ASCII to half-width
    result = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif 0x3000 == code:
            result.append(" ")
        else:
            result.append(ch)
    name = "".join(result)
    # Lowercase ASCII portions
    name = name.lower()
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _parse_aliases(content_json_str: str) -> list[str]:
    """Extract aliases from an atom's content_json.

    Only reads the 'aliases' field — does NOT treat observed_traits as aliases
    (traits are descriptive, not names, and would cause false merges).
    """
    try:
        data = json.loads(content_json_str)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    aliases = data.get("aliases") or []
    if isinstance(aliases, list):
        return [a for a in aliases if isinstance(a, str) and a.strip()]
    return []


def _entity_type_from_atom(atom_type: str) -> str:
    """Map AtomType to EntityType."""
    mapping = {
        AtomType.CHARACTER: "character",
        AtomType.WORLDBUILDING: "location",
    }
    return mapping.get(atom_type, "unknown")


def build_entity_registry(
    topic_id: str,
    session: Session,
    work_ids: list[str] | None = None,
) -> dict:
    """Build or rebuild the topic-level global entity registry.

    Scans ExtractedAtom rows for character/worldbuilding atoms across the full Topic,
    normalizes names, merges deterministically, and creates/updates GlobalEntity +
    EntityMention rows. A scoped request still rebuilds the canonical Topic-wide registry;
    work_ids is retained only for backward-compatible callers.

    Returns a summary dict with counts and warnings.
    """
    warnings: list[str] = []
    if work_ids:
        warnings.append(
            "Entity registry is Topic-wide; requested work_ids did not narrow the rebuild"
        )

    # 1. Load atom-like entities across all Works
    atom_base = select(ExtractedAtom).where(
        ExtractedAtom.topic_id == topic_id,
        ExtractedAtom.atom_type.in_([AtomType.CHARACTER, AtomType.WORLDBUILDING]),
    )

    atoms = session.exec(
        atom_base.order_by(ExtractedAtom.chapter_index, ExtractedAtom.chunk_index)
    ).all()

    if not atoms:
        _clear_registry(topic_id, session)
        invalidated_snapshot_count = _invalidate_graph_snapshots_with_missing_entities(
            topic_id, session, set()
        )
        if invalidated_snapshot_count:
            warnings.append(
                f"Invalidated {invalidated_snapshot_count} graph snapshot(s) with removed entities"
            )
        session.commit()
        return {
            "entity_count": 0,
            "mention_count": 0,
            "invalidated_graph_snapshot_count": invalidated_snapshot_count,
            "warnings": warnings,
        }

    # 2. Build entity groups by normalized key
    # Phase 1: group by stable_id first
    stable_groups: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        stable_groups.setdefault(a.stable_id, []).append(a)

    # Phase 2: merge stable groups by name/alias
    resolved: dict[str, dict] = {}  # entity_key → {atoms, canonical_name, entity_type, ...}

    for stable_id, group in stable_groups.items():
        best = group[0]
        canonical = best.canonical_name or best.title or stable_id
        etype = _entity_type_from_atom(best.atom_type)
        norm = _normalize_name(canonical)

        # Try to match an existing resolved entity
        atom_aliases = []
        for a in group:
            atom_aliases.extend(_parse_aliases(a.content_json))
        matched_key = _find_match(norm, canonical, etype, atom_aliases, resolved)

        if matched_key is not None:
            # Merge into existing
            resolved[matched_key]["atoms"].extend(group)
            resolved[matched_key]["stable_ids"].add(stable_id)
            # Update canonical if the new one is longer/more specific
            if len(canonical) > len(resolved[matched_key]["canonical_name"]):
                resolved[matched_key]["canonical_name"] = canonical
            aliases_list = resolved[matched_key]["aliases"]
            for a in group:
                for alias in _parse_aliases(a.content_json):
                    if alias not in aliases_list:
                        aliases_list.append(alias)
            for a in group:
                wid = _get_work_id_for_atom(a, session)
                if wid:
                    resolved[matched_key]["work_ids"].add(wid)
        else:
            # New entity
            aliases: list[str] = []
            work_ids_set: set[str] = set()
            for a in group:
                for alias in _parse_aliases(a.content_json):
                    if alias not in aliases:
                        aliases.append(alias)
                wid = _get_work_id_for_atom(a, session)
                if wid:
                    work_ids_set.add(wid)

            key = canonical
            if key in resolved:
                # Conflict: same canonical name, different stable_id
                existing = resolved[key]
                if existing["entity_type"] != etype:
                    warnings.append(
                        f"Type conflict: '{canonical}' as {etype} "
                        f"vs {existing['entity_type']}; not merged"
                    )
                    key = f"{canonical} ({stable_id})"
                else:
                    existing["atoms"].extend(group)
                    existing["stable_ids"].add(stable_id)
                    existing["work_ids"].update(work_ids_set)
                    continue

            resolved[key] = {
                "atoms": list(group),
                "stable_ids": {stable_id},
                "canonical_name": canonical,
                "entity_type": etype,
                "aliases": aliases,
                "work_ids": work_ids_set,
                "merge_strategy": "exact",
            }

    reusable_entity_ids = _match_existing_entity_ids(topic_id, session, resolved)
    _clear_registry(topic_id, session)

    # 4. Write GlobalEntity + EntityMention rows
    entity_count = 0
    mention_count = 0
    live_entity_ids: set[str] = set()
    for key, info in resolved.items():
        group_atoms = info["atoms"]

        # Confidence based on merge strategy
        if len(info["stable_ids"]) > 1:
            confidence = 0.78  # normalized match
            merge_strategy = "normalized"
        else:
            confidence = 0.92  # exact stable_id or name match
            merge_strategy = "exact"

        entity_fields = {
            "topic_id": topic_id,
            "entity_type": info["entity_type"],
            "canonical_name": info["canonical_name"],
            "aliases_json": json.dumps(info["aliases"], ensure_ascii=False),
            "work_ids_json": json.dumps(sorted(info["work_ids"]), ensure_ascii=False),
            "mention_count": len(group_atoms),
            "evidence_count": sum(1 for a in group_atoms if _parse_json_list(a.evidence_quotes)),
            "confidence": confidence,
            "merge_strategy": merge_strategy,
            "metadata_json": json.dumps(
                {"stable_ids": sorted(info["stable_ids"])}, ensure_ascii=False
            ),
        }
        reusable_id = reusable_entity_ids.get(key)
        ge = GlobalEntity(
            **entity_fields,
            **({"id": reusable_id} if reusable_id is not None else {}),
        )
        session.add(ge)
        session.flush()
        live_entity_ids.add(ge.id)
        entity_count += 1

        # Mentions
        for a in group_atoms:
            wid = _get_work_id_for_atom(a, session)
            evidence_list = _parse_json_list(a.evidence_quotes)
            em = EntityMention(
                topic_id=topic_id,
                global_entity_id=ge.id,
                work_id=wid or "",
                source_type="atom",
                source_id=a.id,
                chunk_id=a.chunk_id,
                chapter_id=None,
                surface_text=a.canonical_name or "",
                evidence_text=evidence_list[0] if evidence_list else None,
                confidence=a.confidence,
                metadata_json=json.dumps(
                    {"atom_type": a.atom_type, "stable_id": a.stable_id},
                    ensure_ascii=False,
                ),
            )
            session.add(em)
            mention_count += 1

    invalidated_snapshot_count = _invalidate_graph_snapshots_with_missing_entities(
        topic_id, session, live_entity_ids
    )
    if invalidated_snapshot_count:
        warnings.append(
            f"Invalidated {invalidated_snapshot_count} graph snapshot(s) with removed entities"
        )

    session.commit()

    return {
        "entity_count": entity_count,
        "mention_count": mention_count,
        "invalidated_graph_snapshot_count": invalidated_snapshot_count,
        "warnings": warnings,
    }


def _find_match(
    norm_name: str,
    raw_name: str,
    etype: str,
    new_aliases: list[str],
    resolved: dict[str, dict],
) -> str | None:
    """Try to match a normalized name to an existing resolved entity.

    Checks both directions: new name in existing aliases, and existing name in new aliases.
    Returns the key of the matched entity, or None.
    """
    for key, info in resolved.items():
        if info["entity_type"] != etype:
            continue
        # Exact normalized name match
        if _normalize_name(info["canonical_name"]) == norm_name:
            return key
        # Existing entity's aliases contain new name
        for alias in info["aliases"]:
            if _normalize_name(alias) == norm_name:
                return key
        # New entity's aliases contain existing canonical name
        existing_norm = _normalize_name(info["canonical_name"])
        for alias in new_aliases:
            if _normalize_name(alias) == existing_norm:
                return key
        # Raw name match
        if info["canonical_name"] == raw_name:
            return key
    return None


def _get_work_id_for_atom(atom: ExtractedAtom, session: Session) -> str | None:
    """Resolve the Work ID for an atom via its chunk → document path."""
    if atom.chunk_id is None:
        return None
    chunk = session.get(Chunk, atom.chunk_id)
    if chunk is None:
        return None
    doc = session.get(Document, chunk.document_id)
    if doc is None:
        return None
    return doc.work_id


def _parse_json_list(raw: str) -> list:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_dict(raw: str | None) -> dict:
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _match_existing_entity_ids(
    topic_id: str,
    session: Session,
    resolved: dict[str, dict],
) -> dict[str, str]:
    """Reuse IDs for identity-equivalent entity groups so retained graph snapshots stay valid."""
    existing_entities = session.exec(
        select(GlobalEntity).where(GlobalEntity.topic_id == topic_id).order_by(GlobalEntity.id)
    ).all()
    existing_mentions = session.exec(
        select(EntityMention).where(EntityMention.topic_id == topic_id)
    ).all()

    stable_ids_by_entity: dict[str, set[str]] = {entity.id: set() for entity in existing_entities}
    for entity in existing_entities:
        metadata_stable_ids = _parse_json_dict(entity.metadata_json).get("stable_ids", [])
        if isinstance(metadata_stable_ids, list):
            stable_ids_by_entity[entity.id].update(
                stable_id for stable_id in metadata_stable_ids if isinstance(stable_id, str)
            )
    for mention in existing_mentions:
        stable_id = _parse_json_dict(mention.metadata_json).get("stable_id")
        if isinstance(stable_id, str):
            stable_ids_by_entity.setdefault(mention.global_entity_id, set()).add(stable_id)

    existing_identity = []
    for entity in existing_entities:
        names = {_normalize_name(entity.canonical_name)}
        names.update(
            _normalize_name(alias)
            for alias in _parse_json_list(entity.aliases_json)
            if isinstance(alias, str)
        )
        existing_identity.append(
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "canonical_name": _normalize_name(entity.canonical_name),
                "names": {name for name in names if name},
                "stable_ids": stable_ids_by_entity.get(entity.id, set()),
            }
        )

    reusable: dict[str, str] = {}
    used_existing_ids: set[str] = set()
    for key, info in resolved.items():
        new_stable_ids = set(info["stable_ids"])
        new_canonical_name = _normalize_name(info["canonical_name"])
        new_names = {new_canonical_name}
        new_names.update(
            _normalize_name(alias) for alias in info["aliases"] if isinstance(alias, str)
        )
        new_names.discard("")

        candidates: list[tuple[int, str]] = []
        for existing in existing_identity:
            if (
                existing["id"] in used_existing_ids
                or existing["entity_type"] != info["entity_type"]
            ):
                continue

            stable_overlap = new_stable_ids & existing["stable_ids"]
            if stable_overlap:
                score = 100 + len(stable_overlap)
            elif new_canonical_name and new_canonical_name == existing["canonical_name"]:
                score = 50
            elif new_names & existing["names"]:
                score = 25
            else:
                continue
            candidates.append((score, existing["id"]))

        if candidates:
            ranked_candidates = sorted(
                candidates,
                key=lambda candidate: (-candidate[0], candidate[1]),
            )
            _, reusable_id = ranked_candidates[0]
            reusable[key] = reusable_id
            used_existing_ids.add(reusable_id)

    return reusable


def _invalidate_graph_snapshots_with_missing_entities(
    topic_id: str,
    session: Session,
    live_entity_ids: set[str],
) -> int:
    """Delete only snapshots whose serialized node/edge references no longer resolve."""
    snapshots = session.exec(
        select(GraphSnapshot).where(
            GraphSnapshot.topic_id == topic_id,
            GraphSnapshot.graph_type == "character_relationship",
        )
    ).all()
    invalidated = 0
    for snapshot in snapshots:
        if not graph_snapshot_references_are_valid(
            snapshot.nodes_json,
            snapshot.edges_json,
            live_entity_ids,
        ):
            session.delete(snapshot)
            invalidated += 1

    session.flush()
    return invalidated


def graph_snapshot_references_are_valid(
    nodes_json: str,
    edges_json: str,
    live_entity_ids: set[str],
) -> bool:
    """Return whether a serialized graph is structurally valid and entity-linked."""
    nodes = _parse_json_object_list(nodes_json)
    edges = _parse_json_object_list(edges_json)
    if nodes is None or edges is None:
        return False

    node_ids: list[str] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            return False
        node_ids.append(node_id)
    node_id_set = set(node_ids)
    if len(node_id_set) != len(node_ids) or not node_id_set.issubset(live_entity_ids):
        return False

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not source:
            return False
        if not isinstance(target, str) or not target:
            return False
        if source not in node_id_set or target not in node_id_set:
            return False

    return True


def _parse_json_object_list(raw: str) -> list[dict] | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        return None
    return parsed


def _clear_registry(topic_id: str, session: Session) -> None:
    """Delete existing GlobalEntity and EntityMention rows for a topic."""
    from sqlmodel import delete

    session.exec(
        delete(EntityMention).where(EntityMention.topic_id == topic_id)  # type: ignore[arg-type]
    )
    session.exec(
        delete(GlobalEntity).where(GlobalEntity.topic_id == topic_id)  # type: ignore[arg-type]
    )
    session.flush()
