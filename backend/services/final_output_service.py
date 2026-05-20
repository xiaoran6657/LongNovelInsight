"""Convert v0.2 merge results into v0.1/frontend-compatible final AnalysisOutput.

Pure Python — no LLM calls. Each build_final_<type> reads the corresponding
merge output, transforms to a shape matching the existing frontend
AnalysisOutputCard renderers, and writes an AnalysisOutput row.
"""

import json
from dataclasses import dataclass, field

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun


@dataclass
class FinalOutputSummary:
    output_type: str
    item_count: int
    warnings: list[str] = field(default_factory=list)


# ── Helpers ──


def _load_merge_content(session: Session, run_id: str, merge_type: str) -> list[dict]:
    from services.artifact_storage_service import read_json_inline_or_artifact

    out = session.exec(
        select(AnalysisOutput).where(
            AnalysisOutput.run_id == run_id,
            AnalysisOutput.output_type == f"merge_{merge_type}",
        )
    ).first()
    if out is None:
        return []
    try:
        owner_id = f"merge_{merge_type}_{run_id}"
        resolved = read_json_inline_or_artifact(
            session,
            out.content_json,
            "analysis_output",
            owner_id,
        )
        return json.loads(resolved)
    except (json.JSONDecodeError, TypeError):
        return []


def _get_run_topic(session: Session, run_id: str) -> str:
    run = session.get(AnalysisRun, run_id)
    return run.topic_id if run else ""


def _save_final(
    session: Session,
    run_id: str,
    topic_id: str,
    output_type: str,
    title: str,
    content: list | dict,
    source_chunk_ids: list[str],
    evidence_quotes: list[str],
    confidence: float,
) -> AnalysisOutput:
    existing = session.exec(
        select(AnalysisOutput).where(
            AnalysisOutput.run_id == run_id,
            AnalysisOutput.output_type == output_type,
        )
    ).all()
    for old in existing:
        if old.output_type == output_type:
            session.delete(old)

    from services.artifact_storage_service import maybe_store_large_json

    json_str = json.dumps(content, ensure_ascii=False)
    owner_id = f"final_{output_type}_{run_id}"
    stored = maybe_store_large_json(
        session,
        topic_id,
        run_id,
        output_type,
        "analysis_output",
        owner_id,
        json_str,
    )

    out = AnalysisOutput(
        topic_id=topic_id,
        run_id=run_id,
        output_type=output_type,
        title=title,
        content_json=stored,
        source_chunk_ids=json.dumps(source_chunk_ids, ensure_ascii=False),
        evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
        confidence=confidence,
    )
    session.add(out)
    session.commit()
    return out


def _collect_source_chunk_ids(items: list[dict]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        for cid in item.get("source_chunk_ids", []):
            if isinstance(cid, str) and cid not in seen:
                seen.add(cid)
                result.append(cid)
    return result


def _collect_evidence_quotes(items: list[dict]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        for eq in item.get("evidence_quotes", []):
            if isinstance(eq, str) and eq not in seen:
                seen.add(eq)
                result.append(eq)
    return result


def _average_confidence(items: list[dict]) -> float:
    if not items:
        return 0.0
    confs = [c for item in items if (c := item.get("confidence")) is not None]
    if not confs:
        return 0.0
    return round(sum(confs) / len(confs), 4)


# ── Build functions ──


def build_final_overview(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "overview")
    if not items:
        return FinalOutputSummary("overview", 0)

    summary_data = items[0]
    content = {
        "analysis_type": "overview",
        "based_on": "v0.2 merge_overview",
        "summary": (
            f"v0.2 analysis: {summary_data.get('total_atom_count', 0)} atoms extracted "
            f"({summary_data.get('character_count', 0)} characters, "
            f"{summary_data.get('event_count', 0)} events, "
            f"{summary_data.get('relation_count', 0)} relations, "
            f"{summary_data.get('causal_link_count', 0)} causal links, "
            f"{summary_data.get('theme_signal_count', 0)} theme signals)"
        ),
        "total_atoms": summary_data.get("total_atom_count", 0),
        "character_count": summary_data.get("character_count", 0),
        "event_count": summary_data.get("event_count", 0),
        "relation_count": summary_data.get("relation_count", 0),
        "causal_link_count": summary_data.get("causal_link_count", 0),
        "theme_signal_count": summary_data.get("theme_signal_count", 0),
        "worldbuilding_count": summary_data.get("worldbuilding_count", 0),
        "foreshadowing_count": summary_data.get("foreshadowing_count", 0),
        "source_chunk_count": summary_data.get("source_chunk_count", 0),
        "evidence_count": summary_data.get("evidence_count", 0),
    }
    source_ids = summary_data.get("source_chunk_ids", [])
    evidence = summary_data.get("evidence_quotes", [])
    confidence = summary_data.get("confidence", 0.0)

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "overview",
        "Work Overview",
        content,
        source_ids,
        evidence,
        confidence,
    )
    return FinalOutputSummary("overview", 1)


def build_final_characters(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "characters")
    if not items:
        return FinalOutputSummary("characters", 0)

    results = []
    for item in items:
        results.append(
            {
                "name": item.get("canonical_name", ""),
                "stable_id": item.get("stable_id", ""),
                "aliases": item.get("names", []),
                "traits": item.get("traits", []),
                "description": "",
                "role": "",
                "first_appearance_chapter": item.get("first_chapter"),
                "atom_count": item.get("atom_count", 0),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "evidence_quotes": item.get("evidence_quotes", []),
                "confidence": item.get("confidence", 0.0),
            }
        )

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "characters",
        "Character List",
        {
            "analysis_type": "characters",
            "based_on": "v0.2 merge_characters",
            "characters": results,
        },
        _collect_source_chunk_ids(items),
        _collect_evidence_quotes(items),
        _average_confidence(items),
    )
    return FinalOutputSummary("characters", len(results))


def build_final_relations(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "relations")
    if not items:
        return FinalOutputSummary("relations", 0)

    results = []
    for item in items:
        rtype = item.get("relation_type", "")
        results.append(
            {
                "character_a": item.get("character_a", ""),
                "character_b": item.get("character_b", ""),
                "relationship_type": rtype,
                "relation_type": rtype,
                "stable_id": item.get("stable_id", ""),
                "description": "",
                "atom_count": item.get("atom_count", 0),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "evidence_quotes": item.get("evidence_quotes", []),
                "confidence": item.get("confidence", 0.0),
            }
        )

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "relations",
        "Character Relationships",
        {
            "analysis_type": "relations",
            "based_on": "v0.2 merge_relations",
            "relationships": results,
        },
        _collect_source_chunk_ids(items),
        _collect_evidence_quotes(items),
        _average_confidence(items),
    )
    return FinalOutputSummary("relations", len(results))


def build_final_events(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "events")
    if not items:
        return FinalOutputSummary("events", 0)

    results = []
    for item in items:
        results.append(
            {
                "event_id": item.get("stable_id", ""),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "description": item.get("summary", ""),
                "chapter": item.get("first_chapter"),
                "chapter_index": item.get("first_chapter"),
                "chapters": item.get("chapters", []),
                "participants": item.get("participants", []),
                "importance": "",
                "atom_count": item.get("atom_count", 0),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "evidence_quotes": item.get("evidence_quotes", []),
                "confidence": item.get("confidence", 0.0),
            }
        )

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "events",
        "Key Events",
        {
            "analysis_type": "events",
            "based_on": "v0.2 merge_events",
            "events": results,
        },
        _collect_source_chunk_ids(items),
        _collect_evidence_quotes(items),
        _average_confidence(items),
    )
    return FinalOutputSummary("events", len(results))


def build_final_causality(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "causality")
    if not items:
        return FinalOutputSummary("causality", 0)

    results = []
    warnings = []
    for item in items:
        results.append(
            {
                "cause_event_id": item.get("cause_event", ""),
                "effect_event_id": item.get("effect_event", ""),
                "stable_id": item.get("stable_id", ""),
                "causal_description": (
                    item.get("cause_event", "") + " → " + item.get("effect_event", "")
                ),
                "causal_strength": "inferred",
                "resolved": item.get("resolved", False),
                "atom_count": item.get("atom_count", 0),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "evidence_quotes": item.get("evidence_quotes", []),
                "confidence": item.get("confidence", 0.0),
            }
        )
        if not item.get("resolved", False):
            warnings.append(f"Unresolved: {item.get('stable_id', '?')}")

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "causality",
        "Event Causal Chain",
        {
            "analysis_type": "causality",
            "based_on": "v0.2 merge_causality",
            "causal_chains": results,
        },
        _collect_source_chunk_ids(items),
        _collect_evidence_quotes(items),
        _average_confidence(items),
    )
    return FinalOutputSummary("causality", len(results), warnings=warnings)


def build_final_themes(session: Session, run_id: str) -> FinalOutputSummary:
    items = _load_merge_content(session, run_id, "themes")
    if not items:
        return FinalOutputSummary("themes", 0)

    results = []
    for item in items:
        tname = item.get("theme_name", "")
        results.append(
            {
                "theme_name": tname,
                "theme": tname,
                "name": tname,
                "stable_id": item.get("stable_id", ""),
                "signals": item.get("signals", []),
                "description": "",
                "atom_count": item.get("atom_count", 0),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "evidence_quotes": item.get("evidence_quotes", []),
                "confidence": item.get("confidence", 0.0),
            }
        )

    _save_final(
        session,
        run_id,
        _get_run_topic(session, run_id),
        "themes",
        "Themes & Philosophy",
        {
            "analysis_type": "themes",
            "based_on": "v0.2 merge_themes",
            "themes": results,
        },
        _collect_source_chunk_ids(items),
        _collect_evidence_quotes(items),
        _average_confidence(items),
    )
    return FinalOutputSummary("themes", len(results))


# ── Orchestration ──


_FINAL_BUILDERS = {
    "overview": build_final_overview,
    "characters": build_final_characters,
    "relations": build_final_relations,
    "events": build_final_events,
    "causality": build_final_causality,
    "themes": build_final_themes,
}


def run_final_output_stage(
    session: Session,
    run_id: str,
    requested_types: list[str] | None = None,
) -> list[FinalOutputSummary]:
    types_to_run = requested_types or list(_FINAL_BUILDERS)
    summaries: list[FinalOutputSummary] = []

    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"AnalysisRun not found: {run_id}")

    succeeded = 0
    failed = 0
    for output_type in types_to_run:
        if output_type not in _FINAL_BUILDERS:
            summaries.append(
                FinalOutputSummary(output_type, 0, warnings=[f"Unknown final type: {output_type}"])
            )
            continue
        try:
            summary = _FINAL_BUILDERS[output_type](session, run_id)
            summaries.append(summary)
            succeeded += 1
        except Exception as e:
            summaries.append(
                FinalOutputSummary(output_type, 0, warnings=[f"Final output failed: {e}"])
            )
            failed += 1

    run = session.get(AnalysisRun, run_id)
    if run:
        run.final_succeeded = succeeded
        run.final_failed = failed
        session.add(run)
        session.commit()

    return summaries
