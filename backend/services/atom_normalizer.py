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

_ID_HINT_FIELDS: dict[str, list[str]] = {
    AtomType.CHARACTER: ["character_id_hint", "id_hint", "stable_id_hint"],
    AtomType.EVENT: ["event_id_hint", "id_hint", "stable_id_hint"],
    AtomType.RELATION: ["relation_id_hint", "id_hint", "stable_id_hint"],
    AtomType.CAUSAL_LINK: ["causal_link_id_hint", "id_hint", "stable_id_hint"],
    AtomType.THEME_SIGNAL: ["theme_id_hint", "id_hint", "stable_id_hint"],
    AtomType.WORLDBUILDING: ["location_id_hint", "id_hint", "stable_id_hint"],
    AtomType.FORESHADOWING: ["foreshadowing_id_hint", "id_hint", "stable_id_hint"],
    AtomType.OPEN_QUESTION: ["question_id_hint", "id_hint", "stable_id_hint"],
}


@dataclass
class NormalizationSummary:
    created_count: int = 0
    skipped_count: int = 0
    warnings: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Coercion helpers ──


def _coerce_items_list(value: object, json_key: str, summary: NormalizationSummary) -> list[dict]:
    """Coerce an LLM output value into a list of dict items for an atom type key.

    Handles: list of dicts, dict wrapping a list, dict wrapping a single item.
    """
    if value is None:
        return []
    if isinstance(value, list):
        result = [v for v in value if isinstance(v, dict)]
        skipped = len(value) - len(result)
        if skipped:
            summary.warnings.append(f"{json_key}: skipped {skipped} non-dict items")
        return result

    if isinstance(value, dict):
        # Check for known wrapper keys: items/list/results/records/entries
        for wrapper in ("items", "list", "results", "records", "entries"):
            inner = value.get(wrapper)
            if isinstance(inner, list):
                extracted = _coerce_items_list(inner, f"{json_key}.{wrapper}", summary)
                if extracted:
                    return extracted
        # Check if exactly one value is a list
        lists = {k: v for k, v in value.items() if isinstance(v, list)}
        if len(lists) == 1:
            inner = list(lists.values())[0]
            extracted = _coerce_items_list(inner, f"{json_key}._single", summary)
            if extracted:
                return extracted
        # Single atom: the dict looks like one item
        if any(k in value for k in ("name", "title", "character_id_hint", "event_id_hint")):
            return [value]
        summary.warnings.append(
            f"{json_key}: dict wrapping not recognized; keys={list(value.keys())[:5]}"
        )
        return []

    summary.warnings.append(f"{json_key}: expected list or dict, got {type(value).__name__}")
    return []


def _coerce_list(
    value: object,
    field_name: str,
    atom_label: str,
    summary: NormalizationSummary,
) -> list:
    """Coerce a field to a list. Non-list values produce a warning and return [].

    None produces [] with a warning. Missing evidence is flagged explicitly.
    """
    if isinstance(value, list):
        return value
    if value is None:
        summary.warnings.append(f"{atom_label}: {field_name} is missing (None)")
        return []
    summary.warnings.append(
        f"{atom_label}: {field_name} is not a list ({type(value).__name__}), empty list used"
    )
    return []


def _coerce_optional_int(value: object) -> int | None:
    """Safely parse an integer, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ── ID helpers ──


def _extract_id_hint(atom_type: str, item: dict) -> str:
    """Extract an id_hint from an atom item based on its type."""
    fields = _ID_HINT_FIELDS.get(atom_type, ["id_hint", "stable_id_hint"])
    for f in fields:
        v = item.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _build_stable_id(
    atom_type: str,
    item: dict,
    fallback: str,
    existing_ids: set[str],
) -> str:
    """Build a stable ID using type-specific logic.
    Relation: uses character_a/b + relation_type via make_relation_id.
    Causal_link: uses cause_event + effect_event via make_causal_link_id.
    Other types: uses make_stable_id.
    """
    # Relation — use character pair + relation type
    if atom_type == AtomType.RELATION:
        a = _safe_str(
            item.get("character_a_id") or item.get("character_a") or item.get("character_a_hint")
        )
        b = _safe_str(
            item.get("character_b_id") or item.get("character_b") or item.get("character_b_hint")
        )
        rtype = _safe_str(item.get("relation_type") or item.get("interaction_type") or "related")
        if a and b:
            base = stable_id_service.make_relation_id(a, b, rtype)
            return stable_id_service.ensure_unique_stable_id(base, existing_ids)

    # Causal link — use cause + effect event pair
    if atom_type == AtomType.CAUSAL_LINK:
        cause = _safe_str(
            item.get("cause_event_id") or item.get("cause_event") or item.get("cause_hint")
        )
        effect = _safe_str(
            item.get("effect_event_id") or item.get("effect_event") or item.get("effect_hint")
        )
        if cause and effect:
            base = stable_id_service.make_causal_link_id(cause, effect)
            return stable_id_service.ensure_unique_stable_id(base, existing_ids)

    # Default
    id_hint = _extract_id_hint(atom_type, item)
    return stable_id_service.make_stable_id(atom_type, id_hint, fallback, existing_ids)


# ── Title / summary helpers ──


def _safe_str(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def _extract_title(atom_type: str, data: dict) -> str | None:
    field = _TITLE_FIELDS.get(atom_type, "title")
    val = data.get(field)
    if isinstance(val, str) and val.strip():
        return val.strip()
    for f in (
        "name",
        "title",
        "theme_name",
        "label",
        "signal_label",
        "question",
        "interaction_type",
        "link_description",
    ):
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
    """Parse local_extraction JSON and write ExtractedAtom rows."""
    summary = NormalizationSummary()
    existing_ids: set[str] = set()

    # ── Parse top-level JSON ──
    try:
        data = json.loads(content_json_str)
    except (json.JSONDecodeError, TypeError) as e:
        summary.warnings.append(f"Failed to parse content_json: {e}")
        summary.skipped_count = 1
        return summary

    # Handle top-level list
    if isinstance(data, list):
        # Merge all dicts from the list
        merged: dict = {}
        for item in data:
            if isinstance(item, dict):
                for k, v in item.items():
                    if k in merged and isinstance(merged[k], list) and isinstance(v, list):
                        merged[k] = merged[k] + v  # type: ignore[operator]
                    elif k in merged and isinstance(merged[k], list):
                        merged[k] = merged[k] + [v]  # type: ignore[operator]
                    else:
                        merged[k] = v
        if not merged:
            summary.warnings.append("top-level list contains no dict items")
            summary.skipped_count = 1
            return summary
        data = merged

    if not isinstance(data, dict):
        summary.warnings.append(
            f"content_json is not a dict or list of dicts, got {type(data).__name__}"
        )
        summary.skipped_count = 1
        return summary

    chapter_index = _coerce_optional_int(data.get("chapter_index"))

    # ── Process each atom type ──
    for json_key, atom_type in _ATOM_TYPE_MAP.items():
        raw = data.get(json_key)
        if raw is None:
            continue

        items = _coerce_items_list(raw, json_key, summary)
        if not items and raw is not None:
            # coerce_items_list already added warnings
            continue

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                summary.warnings.append(f"{json_key}[{i}]: not a dict, skipping")
                summary.skipped_count += 1
                continue

            atom_label = f"{json_key}[{i}]"

            # Evidence — coerce, warn on missing/non-list
            evidence_quotes = _coerce_list(
                item.get("evidence_quotes"), "evidence_quotes", atom_label, summary
            )
            has_evidence = len(evidence_quotes) > 0

            # Source chunk IDs — coerce, warn on missing/non-list
            source_chunk_ids = _coerce_list(
                item.get("source_chunk_ids"), "source_chunk_ids", atom_label, summary
            )

            # Always ensure current chunk_id is present
            if chunk_id and chunk_id not in source_chunk_ids:
                source_chunk_ids = [chunk_id] + source_chunk_ids

            # Confidence
            conf_raw = item.get("confidence")
            confidence: float
            if conf_raw is None:
                confidence = 0.5
                summary.warnings.append(f"{atom_label}: confidence missing, default 0.5")
            else:
                try:
                    confidence = float(conf_raw)
                except (ValueError, TypeError):
                    confidence = 0.5
                    summary.warnings.append(
                        f"{atom_label}: confidence invalid ({conf_raw}), default 0.5"
                    )
                if confidence < 0.0 or confidence > 1.0:
                    old = confidence
                    confidence = max(0.0, min(1.0, confidence))
                    summary.warnings.append(
                        f"{atom_label}: confidence out of range ({old}), clamped to {confidence}"
                    )

            # No evidence → lower confidence cap
            if not has_evidence and confidence > 0.3:
                summary.warnings.append(
                    f"{atom_label}: no evidence; confidence capped from {confidence} to 0.3"
                )
                confidence = 0.3

            # Title & canonical name
            title = _extract_title(atom_type, item)
            raw_name = (
                item.get("canonical_name")
                or item.get("name")
                or item.get("theme_name")
                or item.get("signal_label")
            )
            canonical_name = _safe_str(raw_name) or None

            # Stable ID
            fallback = title or canonical_name or f"{atom_type}_{i}"
            stable_id = _build_stable_id(atom_type, item, fallback, existing_ids)
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
                chunk_index=_coerce_optional_int(item.get("chunk_index")),
                order_index=i,
            )
            session.add(atom)
            summary.created_count += 1

    return summary
