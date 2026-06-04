"""Deterministic character relationship graph snapshot builder.

Derives edges from relation atoms (primary) or event participant
co-occurrence (fallback). Nodes come from GlobalEntity rows.
No LLM calls.
"""

import json

from sqlmodel import Session, select

from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.global_entity import GlobalEntity
from models.graph_snapshot import GraphSnapshot


def build_character_graph(
    topic_id: str,
    session: Session,
    work_ids: list[str] | None = None,
) -> dict:
    """Build a character relationship graph snapshot for the topic.

    Returns a dict with nodes, edges, stats, and snapshot_id.
    The snapshot is persisted to graph_snapshot table.
    """
    entities = session.exec(
        select(GlobalEntity).where(
            GlobalEntity.topic_id == topic_id,
            GlobalEntity.entity_type == "character",
        )
    ).all()

    # Clear old snapshots first (even if empty — prevents stale reads)
    old_snapshots = session.exec(
        select(GraphSnapshot).where(
            GraphSnapshot.topic_id == topic_id,
            GraphSnapshot.graph_type == "character_relationship",
        )
    ).all()
    for old in old_snapshots:
        session.delete(old)
    session.flush()

    if not entities:
        # Persist an empty snapshot so GET returns empty, not stale
        snapshot = GraphSnapshot(
            topic_id=topic_id,
            graph_type="character_relationship",
            version=1,
            scope_json=json.dumps({"work_ids": work_ids} if work_ids else {}, ensure_ascii=False),
            nodes_json="[]",
            edges_json="[]",
            stats_json=json.dumps({"node_count": 0, "edge_count": 0}, ensure_ascii=False),
        )
        session.add(snapshot)
        session.commit()
        return _empty_graph(topic_id, session, snapshot_id=snapshot.id)

    # Build entity lookup: stable_id → global_entity_id
    # First collect all mention metadata to map atoms → entities
    entity_by_stable: dict[str, str] = {}
    entity_by_name: dict[str, str] = {}
    for e in entities:
        # Parse aliases to build name -> id map
        aliases = _parse_json_list(e.aliases_json)
        for a in aliases:
            entity_by_name[a.lower()] = e.id
        entity_by_name[e.canonical_name.lower()] = e.id

        # Parse mentions metadata for stable_id mappings
        from models.entity_mention import EntityMention

        mentions = session.exec(
            select(EntityMention).where(EntityMention.global_entity_id == e.id)
        ).all()
        for m in mentions:
            meta = _parse_json_dict(m.metadata_json)
            sid = meta.get("stable_id")
            if sid:
                entity_by_stable[sid] = e.id

    # Load relation atoms (filtered by work_ids if provided)
    rel_base = select(ExtractedAtom).where(
        ExtractedAtom.topic_id == topic_id,
        ExtractedAtom.atom_type == AtomType.RELATION,
    )
    if work_ids:
        chunk_ids_subq = (
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.work_id.in_(work_ids))
        )
        rel_base = rel_base.where(ExtractedAtom.chunk_id.in_(chunk_ids_subq))
    relation_atoms = session.exec(rel_base).all()

    # Build edges from relation atoms
    edges: dict[str, dict] = {}  # key = sorted(source, target)
    for atom in relation_atoms:
        content = _parse_json_dict(atom.content_json)
        char_a = content.get("character_a") or content.get("character_a_hint") or ""
        char_b = content.get("character_b") or content.get("character_b_hint") or ""
        rel_type = content.get("relation_type") or content.get("interaction_type") or "related"

        # Map names to global_entity_ids
        src_id = _find_entity_id(char_a, entity_by_name, entity_by_stable)
        tgt_id = _find_entity_id(char_b, entity_by_name, entity_by_stable)
        if not src_id or not tgt_id or src_id == tgt_id:
            continue

        key = tuple(sorted([src_id, tgt_id]))
        if key in edges:
            edges[key]["weight"] += 1
            edges[key]["confidence"] = max(edges[key]["confidence"], atom.confidence)
            edges[key]["relation_type"] = rel_type
            edges[key]["evidence"].append(
                {
                    "chunk_id": atom.chunk_id,
                    "text": (content.get("evidence") or ""),
                }
            )
        else:
            edges[key] = {
                "source": src_id,
                "target": tgt_id,
                "relation_type": rel_type,
                "weight": 1,
                "confidence": atom.confidence,
                "work_ids": set(),
                "evidence": [
                    {
                        "chunk_id": atom.chunk_id,
                        "text": (content.get("evidence") or ""),
                    }
                ],
            }

    # If no relation atoms, fall back to event co-occurrence
    if not edges:
        edges = _build_cooccurrence_edges(
            topic_id, session, entity_by_name, entity_by_stable, work_ids
        )

    # Collect work_ids for edges from evidence atom's chunk → document.work_id
    for key, edge in edges.items():
        wids = set()
        for ev in edge.get("evidence", []):
            cid = ev.get("chunk_id")
            if cid:
                chunk = session.get(Chunk, cid)
                if chunk:
                    doc = session.get(Document, chunk.document_id)
                    if doc and doc.work_id:
                        wids.add(doc.work_id)
        edge["work_ids"] = sorted(wids)

    # Build nodes
    entity_ids_in_graph = set()
    for edge in edges.values():
        entity_ids_in_graph.add(edge["source"])
        entity_ids_in_graph.add(edge["target"])

    nodes = []
    for e in entities:
        if e.id in entity_ids_in_graph:
            nodes.append(
                {
                    "id": e.id,
                    "label": e.canonical_name,
                    "type": e.entity_type,
                    "work_ids": _parse_json_list(e.work_ids_json),
                    "mention_count": e.mention_count,
                    "evidence_count": e.evidence_count,
                    "confidence": e.confidence,
                }
            )

    # Persist snapshot
    edge_list = [
        {
            "id": f"e_{i}",
            "source": e["source"],
            "target": e["target"],
            "relation_type": e["relation_type"],
            "weight": e["weight"],
            "confidence": e["confidence"],
            "work_ids": sorted(e["work_ids"]),
            "evidence": e["evidence"][:3],
        }
        for i, (key, e) in enumerate(edges.items())
    ]

    # Clear old snapshots for this topic+type before persisting new one
    old_snapshots = session.exec(
        select(GraphSnapshot).where(
            GraphSnapshot.topic_id == topic_id,
            GraphSnapshot.graph_type == "character_relationship",
        )
    ).all()
    for old in old_snapshots:
        session.delete(old)

    snapshot = GraphSnapshot(
        topic_id=topic_id,
        graph_type="character_relationship",
        version=1,
        scope_json=json.dumps({"work_ids": work_ids} if work_ids else {}, ensure_ascii=False),
        nodes_json=json.dumps(nodes, ensure_ascii=False),
        edges_json=json.dumps(edge_list, ensure_ascii=False),
        stats_json=json.dumps(
            {"node_count": len(nodes), "edge_count": len(edge_list)},
            ensure_ascii=False,
        ),
    )
    session.add(snapshot)
    session.commit()

    return {
        "graph_type": "character_relationship",
        "nodes": nodes,
        "edges": edge_list,
        "stats": {"node_count": len(nodes), "edge_count": len(edge_list)},
        "snapshot_id": snapshot.id,
        "generated_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


def get_latest_character_graph(
    topic_id: str,
    session: Session,
    work_id: str | None = None,
    min_confidence: float | None = None,
    min_weight: int | None = None,
    relation_type: str | None = None,
    limit_nodes: int | None = None,
    include_evidence: bool = False,
) -> dict:
    """Return the latest character graph snapshot, with optional filters."""
    snapshot = session.exec(
        select(GraphSnapshot)
        .where(
            GraphSnapshot.topic_id == topic_id,
            GraphSnapshot.graph_type == "character_relationship",
        )
        .order_by(GraphSnapshot.created_at.desc())
    ).first()

    if snapshot is None:
        return _empty_graph(topic_id, session)

    nodes = _parse_json_list_obj(snapshot.nodes_json)
    edges = _parse_json_list_obj(snapshot.edges_json)

    # Apply filters
    if work_id:
        nodes = [n for n in nodes if work_id in n.get("work_ids", [])]
        edges = [e for e in edges if work_id in e.get("work_ids", [])]
    if min_confidence is not None:
        edges = [e for e in edges if e.get("confidence", 0) >= min_confidence]
    if min_weight is not None:
        edges = [e for e in edges if e.get("weight", 0) >= min_weight]
    if relation_type:
        edges = [e for e in edges if e.get("relation_type") == relation_type]

    # Keep only nodes referenced by remaining edges
    if edges:
        edge_node_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
        nodes = [n for n in nodes if n["id"] in edge_node_ids]

    if limit_nodes is not None and len(nodes) > limit_nodes:
        # Keep top nodes by mention_count
        nodes = sorted(nodes, key=lambda n: n.get("mention_count", 0), reverse=True)
        nodes = nodes[:limit_nodes]
        kept_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in kept_ids and e["target"] in kept_ids]

    if not include_evidence:
        for e in edges:
            e.pop("evidence", None)

    return {
        "graph_type": "character_relationship",
        "nodes": nodes,
        "edges": edges,
        "stats": _parse_json_dict(snapshot.stats_json),
        "snapshot_id": snapshot.id,
        "generated_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


# ── Helpers ──


def _find_entity_id(
    name: str,
    by_name: dict[str, str],
    by_stable: dict[str, str],
) -> str | None:
    """Map a character name/hint/stable_id to a global_entity_id."""
    if not name.strip():
        return None
    # Direct stable_id match
    if name in by_stable:
        return by_stable[name]
    # Case-insensitive name match
    if name.lower() in by_name:
        return by_name[name.lower()]
    return None


def _build_cooccurrence_edges(
    topic_id: str,
    session: Session,
    by_name: dict[str, str],
    by_stable: dict[str, str],
    work_ids: list[str] | None = None,
) -> dict[str, dict]:
    """Build edges from event atom participant co-occurrence."""
    event_base = select(ExtractedAtom).where(
        ExtractedAtom.topic_id == topic_id,
        ExtractedAtom.atom_type == AtomType.EVENT,
    )
    if work_ids:
        chunk_ids_subq = (
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.work_id.in_(work_ids))
        )
        event_base = event_base.where(ExtractedAtom.chunk_id.in_(chunk_ids_subq))
    event_atoms = session.exec(event_base).all()

    edges: dict[str, dict] = {}
    for atom in event_atoms:
        content = _parse_json_dict(atom.content_json)
        participants = content.get("participants") or []
        if not isinstance(participants, list) or len(participants) < 2:
            continue

        entity_ids = []
        for p in participants:
            if isinstance(p, str):
                eid = _find_entity_id(p, by_name, by_stable)
                if eid:
                    entity_ids.append(eid)

        for i in range(len(entity_ids)):
            for j in range(i + 1, len(entity_ids)):
                key = tuple(sorted([entity_ids[i], entity_ids[j]]))
                if key in edges:
                    edges[key]["weight"] += 1
                else:
                    edges[key] = {
                        "source": entity_ids[i],
                        "target": entity_ids[j],
                        "relation_type": "co_occurrence",
                        "weight": 1,
                        "confidence": atom.confidence * 0.5,
                        "work_ids": set(),
                        "evidence": [
                            {
                                "chunk_id": atom.chunk_id,
                                "text": "",
                            }
                        ],
                    }

    return edges


def _get_entity(
    name_map: dict[str, str],
    key: tuple[str, str],
    session: Session,
) -> GlobalEntity | None:
    for eid in key:
        entity = session.get(GlobalEntity, eid)
        if entity:
            return entity
    return None


def _empty_graph(topic_id: str, session: Session, snapshot_id: str | None = None) -> dict:
    return {
        "graph_type": "character_relationship",
        "nodes": [],
        "edges": [],
        "stats": {"node_count": 0, "edge_count": 0},
        "snapshot_id": snapshot_id,
        "generated_at": None,
    }


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


def _parse_json_list_obj(raw: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
