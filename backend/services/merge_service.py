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
    out = AnalysisOutput(
        topic_id=topic_id,
        run_id=run_id,
        output_type=f"merge_{merge_type}",
        title=f"Merged {merge_type}",
        content_json=json.dumps(result, ensure_ascii=False),
        source_chunk_ids=json.dumps(source_chunk_ids, ensure_ascii=False),
        evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
        confidence=confidence,
    )
    session.add(out)
    return out


# ── Merge functions ──


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
                for al in (c.get("aliases") or c.get("observed_traits") or []):
                    if al not in traits:
                        traits.append(al)

        chapter_indices = [a.chapter_index for a in group if a.chapter_index is not None]
        chunk_indices = [a.chunk_index for a in group if a.chunk_index is not None]

        merged.append({
            "stable_id": stable_id,
            "canonical_name": group[0].canonical_name or (names[0] if names else stable_id),
            "names": names,
            "traits": traits,
            "atom_count": len(group),
            "first_chapter": min(chapter_indices) if chapter_indices else None,
            "first_chunk": min(chunk_indices) if chunk_indices else None,
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "characters", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
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
                for p in (c.get("participants") or []):
                    if isinstance(p, str):
                        participants.add(p)

        chapter_indices = [a.chapter_index for a in group if a.chapter_index is not None]
        merged.append({
            "stable_id": stable_id,
            "title": group[0].title or stable_id,
            "summary": group[0].summary or "",
            "participants": sorted(participants),
            "atom_count": len(group),
            "first_chapter": min(chapter_indices) if chapter_indices else None,
            "chapters": sorted(set(a.chapter_index for a in group if a.chapter_index is not None)),
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "events", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
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
                character_a = character_a or c.get("character_a", "")
                character_b = character_b or c.get("character_b", "")
                relation_type = relation_type or c.get("relation_type", "")

        merged.append({
            "stable_id": stable_id,
            "character_a": character_a,
            "character_b": character_b,
            "relation_type": relation_type,
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "relations", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("relations", len(atoms), len(merged))


def merge_causality(session: Session, run_id: str) -> MergeSummary:
    atoms = _load_atoms(session, run_id, AtomType.CAUSAL_LINK)
    if not atoms or len(atoms) == 0:
        return MergeSummary("causality", 0, 0)

    grouped: dict[str, list[ExtractedAtom]] = {}
    for a in atoms:
        grouped.setdefault(a.stable_id, []).append(a)

    # Collect all event IDs for reference validation
    all_events = {a.stable_id for a in _load_atoms(session, run_id, AtomType.EVENT)}
    unresolved: list[str] = []

    merged = []
    for stable_id, group in grouped.items():
        content_list = [_parse_json(a.content_json) for a in group]
        cause = ""
        effect = ""
        for c in content_list:
            if isinstance(c, dict):
                cause = cause or c.get("cause_event", c.get("cause_event_id", ""))
                effect = effect or c.get("effect_event", c.get("effect_event_id", ""))

        is_resolved = (cause in all_events) and (effect in all_events)
        if not is_resolved:
            unresolved.append(f"{stable_id}: cause={cause}, effect={effect}")

        merged.append({
            "stable_id": stable_id,
            "cause_event": cause,
            "effect_event": effect,
            "resolved": is_resolved,
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
        })

    warnings = []
    if unresolved:
        warnings.append(f"{len(unresolved)} unresolved causal links: " + "; ".join(unresolved[:5]))

    _save_merged(
        session, run_id, atoms[0].topic_id, "causality", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
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

        merged.append({
            "stable_id": stable_id,
            "theme_name": theme_name,
            "signals": signals or [stable_id],
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "themes", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
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
        merged.append({
            "stable_id": stable_id,
            "name": group[0].canonical_name or stable_id,
            "description": group[0].summary or "",
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "worldbuilding", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
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

        merged.append({
            "stable_id": stable_id,
            "title": group[0].title or stable_id,
            "signal": signal,
            "possible_payoff": payoff,
            "atom_count": len(group),
            "source_atom_ids": [a.id for a in group],
        })

    _save_merged(
        session, run_id, atoms[0].topic_id, "foreshadowing", merged,
        [a.id for a in atoms], _collect_source_ids(atoms), _collect_evidence(atoms),
        _average_confidence(atoms),
    )
    return MergeSummary("foreshadowing", len(atoms), len(merged))


# ── Orchestration ──


_MERGE_TYPES = {
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
    summaries = []

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"AnalysisRun not found: {run_id}")

    total = 0
    succeeded = 0
    for merge_type in types_to_run:
        if merge_type not in _MERGE_TYPES:
            continue
        try:
            summary = _MERGE_TYPES[merge_type](session, run_id)
            summaries.append(summary)
            total += 1
            if summary.merged_count >= 0:
                succeeded += 1
        except Exception as e:
            summaries.append(
                MergeSummary(merge_type, 0, 0, warnings=[f"Merge failed: {e}"])
            )

    # Update run progress
    run.merge_total = total
    run.merge_succeeded = succeeded
    run.merge_failed = total - succeeded
    run.progress_current = (run.extraction_succeeded or 0) + (run.extraction_failed or 0) + succeeded
    session.add(run)
    session.commit()

    return summaries
