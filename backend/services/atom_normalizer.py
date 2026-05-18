"""Normalize local_extraction JSON into ExtractedAtom rows.

Pure Python service. No LLM calls. Designed to be fault-tolerant:
malformed individual atoms are skipped with warnings, not causing
the entire chunk's normalization to fail.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session

from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from services import stable_id_service

logger = logging.getLogger(__name__)

_ATOM_TYPE_MAP: dict[str, str] = {
    "local_characters": AtomType.CHARACTER,
    "local_events": AtomType.EVENT,
    "local_relations": AtomType.RELATION,
    "local_causal_links": AtomType.CAUSAL_LINK,
    "local_theme_signals": AtomType.THEME_SIGNAL,
    "local_worldbuilding": AtomType.WORLDBUILDING,
    "local_foreshadowing": AtomType.FORESHADOWING,
    "local_open_questions": AtomType.OPEN_QUESTION,
}

_TITLE_FIELDS: dict[str, str] = {
    AtomType.CHARACTER: "name",
    AtomType.EVENT: "title",
    AtomType.RELATION: "relation_type",
    AtomType.CAUSAL_LINK: "title",
    AtomType.THEME_SIGNAL: "theme_name",
    AtomType.WORLDBUILDING: "name",
    AtomType.FORESHADOWING: "title",
    AtomType.OPEN_QUESTION: "title",
}


@dataclass
class NormalizationSummary:
    created_count: int = 0
    skipped_count: int = 0
    warnings: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Per-atom helper ──


def _safe_str(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def _safe_float(value: object, default: float = 0.5) -> float:
    if value is None:
        return default
    try:
        v = float(value)
        return max(0.0, min(1.0, v))
    except (ValueError, TypeError):
        return default


def _safe_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return []


def _extract_title(atom_type: str, data: dict) -> str | None:
    field = _TITLE_FIELDS.get(atom_type, "title")
    val = data.get(field)
    if isinstance(val, str) and val.strip():
        return val.strip()
    # fallback: try common fields
    for f in ("name", "title", "theme_name", "label"):
        v = data.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _extract_summary(atom_type: str, data: dict) -> str | None:
    for f in ("brief_description", "summary", "description", "notes"):
        v = data.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


# ── Main normalize function ──


def normalize_local_extraction(
    extraction_id: str,
    run_id: str,
    topic_id: str,
    chunk_id: str | None,
    content_json_str: str,
    session: Session,
) -> NormalizationSummary:
    """Parse local_extraction JSON and write ExtractedAtom rows.

    Returns a summary with counts and warnings.
    Existing atoms for this extraction_id are NOT auto-deleted; callers
    should handle idempotency (e.g. delete first if force re-run).
    """
    summary = NormalizationSummary()
    existing_ids: set[str] = set()

    # Parse JSON
    try:
        data = json.loads(content_json_str)
    except (json.JSONDecodeError, TypeError) as e:
        summary.warnings.append(f"Failed to parse content_json: {e}")
        summary.skipped_count = 1
        return summary

    if not isinstance(data, dict):
        # Maybe a list wrapping
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            summary.warnings.append("content_json is not a dict or list of dicts")
            summary.skipped_count = 1
            return summary

    chapter_index = data.get("chapter_index")
    if chapter_index is not None:
        try:
            chapter_index = int(chapter_index)
        except (ValueError, TypeError):
            chapter_index = None

    for json_key, atom_type in _ATOM_TYPE_MAP.items():
        items = data.get(json_key)
        if items is None:
            continue
        if isinstance(items, dict):
            # Some LLMs wrap single-item results in a dict
            items = list(items.values()) if items else []
        if not isinstance(items, list):
            summary.warnings.append(f"{json_key} is not a list, got {type(items).__name__}")
            continue

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                summary.warnings.append(f"{json_key}[{i}]: not a dict, skipping")
                summary.skipped_count += 1
                continue

            # Extract id_hint
            id_hint = _safe_str(item.get("character_id_hint") or item.get("event_id_hint")
                                or item.get("relation_id_hint") or item.get("causal_link_id_hint")
                                or item.get("theme_id_hint") or item.get("location_id_hint")
                                or item.get("foreshadowing_id_hint") or item.get("question_id_hint")
                                or item.get("stable_id_hint"))

            # Title & summary
            title = _extract_title(atom_type, item)
            raw_name = item.get("canonical_name") or item.get("name") or item.get("theme_name")
            canonical_name = _safe_str(raw_name) or None

            # Evidence
            evidence_quotes = _safe_list(item.get("evidence_quotes"))
            source_chunk_ids = _safe_list(item.get("source_chunk_ids"))

            # Ensure current chunk_id is in source
            if chunk_id and chunk_id not in source_chunk_ids:
                source_chunk_ids = [chunk_id] + source_chunk_ids

            confidence = _safe_float(item.get("confidence"))

            # Fallback text for stable ID
            fallback = title or canonical_name or f"{atom_type}_{i}"

            # Generate stable ID
            stable_id = stable_id_service.make_stable_id(
                atom_type=atom_type,
                id_hint=id_hint,
                fallback_text=fallback,
                existing_ids=existing_ids,
            )
            existing_ids.add(stable_id)

            # Write ExtractedAtom
            atom = ExtractedAtom(
                run_id=run_id,
                topic_id=topic_id,
                local_extraction_id=extraction_id,
                chunk_id=chunk_id,
                atom_type=atom_type,
                stable_id=stable_id,
                canonical_name=canonical_name,
                title=title,
                summary=_extract_summary(atom_type, item),
                content_json=json.dumps(item, ensure_ascii=False),
                source_chunk_ids=json.dumps(source_chunk_ids, ensure_ascii=False),
                evidence_quotes=json.dumps(evidence_quotes, ensure_ascii=False),
                confidence=confidence,
                chapter_index=chapter_index,
                chunk_index=item.get("chunk_index"),
                order_index=i,
            )
            session.add(atom)
            summary.created_count += 1

    return summary
