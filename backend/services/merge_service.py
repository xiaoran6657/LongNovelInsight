"""Deterministic merge of ExtractedAtoms into global intermediate results.

Pure Python — no LLM calls. Each merge_<type> function deduplicates
and consolidates atoms by stable_id, then writes interim AnalysisOutput
rows with output_type = "merge_<type>".
"""

import json
from dataclasses import dataclass, field

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom


@dataclass
class MergeSummary:
    merge_type: str
    atom_count: int
    merged_count: int
    warnings: list[str] = field(default_factory=list)


# ── Helpers ──


def _load_atoms(session: Session, run_id: str, atom_type: str) -> list[ExtractedAtom]:
    return list(
        session.exec(
            select(ExtractedAtom)
            .where(ExtractedAtom.run_id == run_id)
            .where(ExtractedAtom.atom_type == atom_type)
            .order_by(ExtractedAtom.chapter_index, ExtractedAtom.chunk_index)
        ).all()
    )


def _parse_json(val: str) -> list | dict:
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _average_confidence(atoms: list[ExtractedAtom]) -> float:
    if not atoms:
        return 0.0
    return round(sum(a.confidence for a in atoms) / len(atoms), 4)


def _collect_source_ids(atoms: list[ExtractedAtom]) -> list[str]:
    seen = set()
    result = []
    for a in atoms:
        for cid in _parse_json(a.source_chunk_ids):
            if isinstance(cid, str) and cid not in seen:
                seen.add(cid)
                result.append(cid)
    return result


def _collect_evidence(atoms: list[ExtractedAtom]) -> list[str]:
    seen = set()
    result = []
    for a in atoms:
        for eq in _parse_json(a.evidence_quotes):
            if isinstance(eq, str) and eq not in seen:
                seen.add(eq)
                result.append(eq)
    return result


def _group_source_chunk_ids(group: list[ExtractedAtom]) -> list[str]:
    seen = set()
    result = []
    for a in group:
        for cid in _parse_json(a.source_chunk_ids):
            if isinstance(cid, str) and cid not in seen:
                seen.add(cid)
                result.append(cid)
    return result


def _group_evidence_quotes(group: list[ExtractedAtom]) -> list[str]:
    seen = set()
    result = []
    for a in group:
        for eq in _parse_json(a.evidence_quotes):
            if isinstance(eq, str) and eq not in seen:
                seen.add(eq)
                result.append(eq)
    return result


def _save_merged(
    session: Session,
    run_id: str,
    topic_id: str,
    merge_type: str,
    result: list[dict],
    source_atom_ids: list[str],
    source_chunk_ids: list[str],
    evidence_quotes: list[str],
    confidence: float,
) -> AnalysisOutput:
    # Delete previous merge output for this run+type to avoid duplicates
    existing = session.exec(
        select(AnalysisOutput).where(
            AnalysisOutput.run_id == run_id,
            AnalysisOutput.output_type == f"merge_{merge_type}",
        )
    ).all()
    for old in existing:
        session.delete(old)

    json_str = json.dumps(result, ensure_ascii=False)
    from services.artifact_storage_service import maybe_store_large_json

    stored = maybe_store_large_json(
        session,
        topic_id,
        run_id,
        f"merge_{merge_type}",
        "analysis_output",
        f"merge_{merge_type}_{run_id}",
        json_str,
    )

    out = AnalysisOutput(
        topic_id=topic_id,
        run_id=run_id,
        output_type=f"merge_{merge_type}",
        title=f"Merged {merge_type}",
        content_json=stored,
        source_chunk_ids=json.dumps(source_chunk_ids, ensure_ascii=False),
        evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
        confidence=confidence,
    )
    session.add(out)
    session.commit()
    return out


# ── Merge functions ──


def merge_overview(session: Session, run_id: str) -> MergeSummary:
    """Statistical overview of all extracted atoms in this run. No LLM."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return MergeSummary("overview", 0, 0, warnings=["AnalysisRun not found"])

    counts: dict[str, int] = {}
    all_chunk_ids: set[str] = set()
    all_evidence: set[str] = set()
    all_atom_ids: list[str] = []
    all_atoms: list[ExtractedAtom] = []

    for atom_type in AtomType:
        atoms = _load_atoms(session, run_id, atom_type.value)
        counts[atom_type.value] = len(atoms)
        all_atoms.extend(atoms)
        for a in atoms:
            all_atom_ids.append(a.id)
            for cid in _parse_json(a.source_chunk_ids):
                if isinstance(cid, str):
                    all_chunk_ids.add(cid)
            for eq in _parse_json(a.evidence_quotes):
                if isinstance(eq, str):
                    all_evidence.add(eq)

    total_atoms = sum(counts.values())
    sorted_chunk_ids = sorted(all_chunk_ids)
    sorted_evidence = sorted(all_evidence)
    avg_confidence = _average_confidence(all_atoms) if all_atoms else 0.0
    merged = [
        {
            "stable_id": f"overview_{run_id[:8]}",
            "character_count": counts.get("character", 0),
            "event_count": counts.get("event", 0),
            "relation_count": counts.get("relation", 0),
            "causal_link_count": counts.get("causal_link", 0),
            "theme_signal_count": counts.get("theme_signal", 0),
            "worldbuilding_count": counts.get("worldbuilding", 0),
            "foreshadowing_count": counts.get("foreshadowing", 0),
            "open_question_count": counts.get("open_question", 0),
            "total_atom_count": total_atoms,
            "source_chunk_count": len(sorted_chunk_ids),
            "evidence_count": len(sorted_evidence),
            "source_atom_ids": all_atom_ids[:100],
            "source_chunk_ids": sorted_chunk_ids,
            "evidence_quotes": sorted_evidence,
            "confidence": avg_confidence,
        }
    ]

    if not all_atom_ids:
        _save_merged(
            session,
            run_id,
            run.topic_id,
            "overview",
            merged,
            [],
            [],
            [],
            0.0,
        )
        return MergeSummary("overview", 0, 0)

    _save_merged(
        session,
        run_id,
        run.topic_id,
        "overview",
        merged,
        all_atom_ids,
        sorted(all_chunk_ids),
        sorted(all_evidence),
        _average_confidence(all_atoms),
    )
    return MergeSummary("overview", total_atoms, 1)


def merge_characters(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.CHARACTER)
    if not atoms:
        return MergeSummary("characters", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        names = []
        traits = []
        for c in content_list:
            if isinstance(c, dict):
                n = c.get("name") or c.get("canonical_name")
                if n and n not in names:
                    names.append(n)
                for al in c.get("aliases") or c.get("observed_traits") or []:
                    if al not in traits:
                        traits.append(al)

        chapter_indices = [a.chapter_index for a in group if a.chapter_index is not None]
        chunk_indices = [a.chunk_index for a in group if a.chunk_index is not None]

        merged.append(
            {
                "stable_id": stable_id,
                "canonical_name": group[0].canonical_name or (names[0] if names else stable_id),
                "names": names,
                "traits": traits,
                "atom_count": len(group),
                "first_chapter": min(chapter_indices) if chapter_indices else None,
                "first_chunk": min(chunk_indices) if chunk_indices else None,
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "characters",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("characters", len(atoms), len(merged))


def merge_events(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.EVENT)
    if not atoms:
        return MergeSummary("events", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        participants = set()
        for c in (_parse_json(a.content_json) for a in group):
            if isinstance(c, dict):
                for p in c.get("participants") or []:
                    if isinstance(p, str):
                        participants.add(p)

        chapter_indices = [a.chapter_index for a in group if a.chapter_index is not None]
        merged.append(
            {
                "stable_id": stable_id,
                "title": group[0].title or stable_id,
                "summary": group[0].summary or "",
                "participants": sorted(participants),
                "atom_count": len(group),
                "first_chapter": min(chapter_indices) if chapter_indices else None,
                "chapters": sorted(
                    set(a.chapter_index for a in group if a.chapter_index is not None)
                ),
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "events",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("events", len(atoms), len(merged))


def merge_relations(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.RELATION)
    if not atoms:
        return MergeSummary("relations", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        character_a = ""
        character_b = ""
        relation_type = ""
        for c in content_list:
            if isinstance(c, dict):
                character_a = (
                    character_a or c.get("character_a", "") or c.get("character_a_hint", "")
                )
                character_b = (
                    character_b or c.get("character_b", "") or c.get("character_b_hint", "")
                )
                relation_type = (
                    relation_type or c.get("relation_type", "") or c.get("interaction_type", "")
                )

        merged.append(
            {
                "stable_id": stable_id,
                "character_a": character_a,
                "character_b": character_b,
                "relation_type": relation_type,
                "atom_count": len(group),
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "relations",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("relations", len(atoms), len(merged))


def _normalize_match_key(s: str) -> str:
    """Lowercase, strip, collapse whitespace for fuzzy matching."""
    return " ".join(s.lower().split())


def _build_event_index(
    session: Session, run_id: str
) -> dict[str, list[dict]]:
    """Build lookup index from event atoms: stable_id → [{field: value}].

    Each entry has: stable_id, title, summary, id_hints (from content_json).
    Title is sourced from ExtractedAtom.title first, then content_json["title"].
    """
    events = _load_atoms(session, run_id, AtomType.EVENT)
    index: dict[str, list[dict]] = {}
    for ev in events:
        c = _parse_json(ev.content_json)
        if not isinstance(c, dict):
            c = {}
        title = (ev.title or c.get("title") or "").strip()
        summary = (ev.summary or c.get("summary") or "").strip()
        id_hints = []
        for k in ("event_id_hint", "id_hint", "stable_id_hint"):
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                id_hints.append(v.strip())
        entry = {
            "stable_id": ev.stable_id,
            "title": title,
            "summary": summary,
            "id_hints": id_hints,
        }
        index.setdefault(ev.stable_id, []).append(entry)
    return index


def _match_causal_side(
    raw: str, event_index: dict[str, list[dict]]
) -> tuple[bool, str | None]:
    """Try to match a cause/effect string to an event stable_id.

    Returns (resolved, stable_id_or_None).
    """
    if not raw or not raw.strip():
        return False, None
    raw_norm = _normalize_match_key(raw)
    if len(raw_norm) < 4:
        return False, None

    for stable_id, entries in event_index.items():
        for e in entries:
            # Direct stable_id match
            if raw_norm == _normalize_match_key(stable_id):
                return True, stable_id
            # Direct title match
            title_norm = _normalize_match_key(e["title"])
            if title_norm and raw_norm == title_norm:
                return True, stable_id
            # Direct id_hint match
            for hint in e["id_hints"]:
                if raw_norm == _normalize_match_key(hint):
                    return True, stable_id
            # Contains: cause text contains title (title len >= 4)
            if title_norm and len(title_norm) >= 4 and title_norm in raw_norm:
                return True, stable_id
            # Reverse contains: title contains cause text (cause len >= 4)
            if title_norm and len(title_norm) >= 4 and raw_norm in title_norm:
                return True, stable_id
            # Summary contains
            summary_norm = _normalize_match_key(e["summary"])
            if summary_norm and len(summary_norm) >= 4 and len(raw_norm) >= 4:
                if raw_norm in summary_norm or summary_norm in raw_norm:
                    return True, stable_id
    return False, None


def merge_causality(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.CAUSAL_LINK)
    if not atoms or len(atoms) == 0:
        return MergeSummary("causality", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    event_index = _build_event_index(session, run_id)
    unresolved: list[str] = []

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        cause = ""
        effect = ""
        cause_event_id = ""
        effect_event_id = ""
        for c in content_list:
            if isinstance(c, dict):
                cause = cause or c.get(
                    "cause_event", c.get("cause_event_id", c.get("cause_hint", ""))
                )
                effect = effect or c.get(
                    "effect_event", c.get("effect_event_id", c.get("effect_hint", ""))
                )
                cause_event_id = cause_event_id or c.get("cause_event_id", "")
                effect_event_id = effect_event_id or c.get("effect_event_id", "")

        cause_resolved, cause_sid = _match_causal_side(cause, event_index)
        if not cause_resolved and cause_event_id:
            cause_resolved, cause_sid = _match_causal_side(cause_event_id, event_index)
        effect_resolved, effect_sid = _match_causal_side(effect, event_index)
        if not effect_resolved and effect_event_id:
            effect_resolved, effect_sid = _match_causal_side(effect_event_id, event_index)

        is_resolved = cause_resolved and effect_resolved
        if not is_resolved:
            unresolved.append(f"{stable_id}: cause={cause[:60]}, effect={effect[:60]}")

        merged_item = {
            "stable_id": stable_id,
            "cause_event": cause,
            "effect_event": effect,
            "resolved": is_resolved,
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
            "source_chunk_ids": _group_source_chunk_ids(group),
            "evidence_quotes": _group_evidence_quotes(group),
            "confidence": _average_confidence(group),
        }
        if cause_sid:
            merged_item["resolved_cause_event_id"] = cause_sid
        if effect_sid:
            merged_item["resolved_effect_event_id"] = effect_sid
        merged.append(merged_item)

    warnings = []
    if unresolved:
        warnings.append(f"{len(unresolved)} unresolved causal links: " + "; ".join(unresolved[:5]))

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "causality",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("causality", len(atoms), len(merged), warnings=warnings)


def merge_themes(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.THEME_SIGNAL)
    if not atoms:
        return MergeSummary("themes", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        theme_name = group[0].canonical_name or stable_id
        signals = []
        for c in content_list:
            if isinstance(c, dict):
                n = c.get("theme_name")
                if n and n not in signals:
                    signals.append(n)

        merged.append(
            {
                "stable_id": stable_id,
                "theme_name": theme_name,
                "signals": signals or [stable_id],
                "atom_count": len(group),
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "themes",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("themes", len(atoms), len(merged))


def merge_worldbuilding(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.WORLDBUILDING)
    if not atoms:
        return MergeSummary("worldbuilding", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        merged.append(
            {
                "stable_id": stable_id,
                "name": group[0].canonical_name or stable_id,
                "description": group[0].summary or "",
                "atom_count": len(group),
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "worldbuilding",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("worldbuilding", len(atoms), len(merged))


def merge_foreshadowing(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.FORESHADOWING)
    if not atoms:
        return MergeSummary("foreshadowing", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        signal = ""
        payoff = ""
        for c in content_list:
            if isinstance(c, dict):
                signal = signal or c.get("signal", "")
                payoff = payoff or c.get("possible_payoff", "")

        merged.append(
            {
                "stable_id": stable_id,
                "title": group[0].title or stable_id,
                "signal": signal,
                "possible_payoff": payoff,
                "atom_count": len(group),
                "source_atom_ids": [a.id for a in group],
                "source_chunk_ids": _group_source_chunk_ids(group),
                "evidence_quotes": _group_evidence_quotes(group),
                "confidence": _average_confidence(group),
            }
        )

    _save_merged(
        session,
        run_id,
        atoms[0].topic_id,
        "foreshadowing",
        merged,
        [a.id for a in atoms],
        _collect_source_ids(atoms),
        _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("foreshadowing", len(atoms), len(merged))


# ── Orchestration ──


_MERGE_TYPES = {
    "overview": merge_overview,
    "characters": merge_characters,
    "events": merge_events,
    "relations": merge_relations,
    "causality": merge_causality,
    "themes": merge_themes,
    "worldbuilding": merge_worldbuilding,
    "foreshadowing": merge_foreshadowing,
}


def run_merge_stage(
    session: Session,
    run_id: str,
    requested_types: list[str] | None = None,
) -> list[MergeSummary]:
    """Run all requested merge types and return summaries."""
    types_to_run = requested_types or list(_MERGE_TYPES)
    summaries: list[MergeSummary] = []

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"AnalysisRun not found: {run_id}")

    total = 0
    succeeded = 0
    for merge_type in types_to_run:
        if merge_type not in _MERGE_TYPES:
            summaries.append(
                MergeSummary(
                    merge_type,
                    0,
                    0,
                    warnings=[f"Unknown merge type: {merge_type}"],
                )
            )
            continue
        try:
            summary = _MERGE_TYPES[merge_type](session, run_id)
            summaries.append(summary)
            total += 1
            succeeded += 1
        except Exception as e:
            summaries.append(MergeSummary(merge_type, 0, 0, warnings=[f"Merge failed: {e}"]))

    run.merge_total = total
    run.merge_succeeded = succeeded
    run.merge_failed = total - succeeded
    session.add(run)
    session.commit()

    return summaries
