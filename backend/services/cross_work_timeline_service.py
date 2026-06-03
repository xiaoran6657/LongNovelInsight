"""Deterministic cross-work timeline builder from event atoms.

Orders events by: explicit sequence → chunk order → Work series_index +
chapter/chunk order. No LLM calls.
"""

import json

from sqlmodel import Session, select

from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.timeline_item import TimelineItem


def build_timeline(
    topic_id: str,
    session: Session,
    work_ids: list[str] | None = None,
) -> dict:
    """Build or rebuild the cross-work timeline from event atoms.

    Returns a dict with item count and any warnings.
    """
    # Clear existing timeline for this topic
    from sqlmodel import delete

    session.exec(
        delete(TimelineItem).where(TimelineItem.topic_id == topic_id)  # type: ignore[arg-type]
    )
    session.flush()

    # Load event atoms
    base = select(ExtractedAtom).where(
        ExtractedAtom.topic_id == topic_id,
        ExtractedAtom.atom_type == AtomType.EVENT,
    )

    if work_ids:
        chunk_ids_subq = (
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.work_id.in_(work_ids))
        )
        base = base.where(ExtractedAtom.chunk_id.in_(chunk_ids_subq))

    event_atoms = session.exec(
        base.order_by(ExtractedAtom.chapter_index, ExtractedAtom.chunk_index)
    ).all()

    if not event_atoms:
        return {"item_count": 0, "warnings": []}

    # Build work_index lookup for ordering
    docs = session.exec(select(Document).where(Document.topic_id == topic_id)).all()
    work_series: dict[str, int] = {}
    for d in docs:
        if d.work_id:
            from models.work import Work as WorkModel

            w = session.get(WorkModel, d.work_id)
            work_series[d.id] = w.series_index if w and w.series_index else 1

    # Build chunk lookup for ordering
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
    chunk_info: dict[str, tuple] = {}
    for c in chunks:
        chunk_info[c.id] = (c.chapter_index or 0, c.chunk_index or 0)

    # Compute sequence_index and create TimelineItems
    items_created = 0
    for atom in event_atoms:
        content = _parse_json_dict(atom.content_json)
        title = content.get("title") or atom.title or "Untitled Event"
        summary = atom.summary or content.get("summary") or ""
        participants = content.get("participants") or []
        locations = content.get("locations") or []

        # Compute document/work for this chunk
        doc_id = None
        work_id = None
        if atom.chunk_id and atom.chunk_id in chunk_info:
            c = session.get(Chunk, atom.chunk_id)
            if c:
                doc_id = c.document_id
                if doc_id:
                    d = session.get(Document, doc_id)
                    if d:
                        work_id = d.work_id

        # Sequence: work_series * 1_000_000 + chapter * 1000 + chunk
        ws = work_series.get(doc_id or "", 1)
        ci, chi = chunk_info.get(atom.chunk_id or "", (0, 0))
        sequence = ws * 1_000_000 + ci * 1000 + chi

        evidence_list = _parse_json_list(atom.evidence_quotes)

        item = TimelineItem(
            topic_id=topic_id,
            work_id=work_id,
            event_atom_id=atom.id,
            title=title,
            summary=summary[:500] if summary else None,
            sequence_index=sequence,
            time_label=content.get("time_label"),
            participants_json=json.dumps(
                participants if isinstance(participants, list) else [],
                ensure_ascii=False,
            ),
            locations_json=json.dumps(
                locations if isinstance(locations, list) else [],
                ensure_ascii=False,
            ),
            causes_json=json.dumps([], ensure_ascii=False),
            effects_json=json.dumps([], ensure_ascii=False),
            evidence_json=json.dumps(
                evidence_list[:3] if evidence_list else [],
                ensure_ascii=False,
            ),
            confidence=atom.confidence,
        )
        session.add(item)
        items_created += 1

    session.commit()

    return {"item_count": items_created, "warnings": []}


def get_timeline(
    topic_id: str,
    session: Session,
    work_id: str | None = None,
    participant_entity_id: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return timeline items with optional filters."""
    base = select(TimelineItem).where(TimelineItem.topic_id == topic_id)

    if work_id:
        base = base.where(TimelineItem.work_id == work_id)
    if min_confidence is not None:
        base = base.where(TimelineItem.confidence >= min_confidence)
    if participant_entity_id:
        base = base.where(
            TimelineItem.participants_json.contains(participant_entity_id)  # type: ignore[arg-type]
        )

    total = len(session.exec(base).all())
    items = session.exec(
        base.order_by(TimelineItem.sequence_index).offset(offset).limit(limit)
    ).all()

    return {
        "items": [
            {
                "id": i.id,
                "work_id": i.work_id,
                "title": i.title,
                "summary": i.summary,
                "sequence_index": i.sequence_index,
                "time_label": i.time_label,
                "participants": _parse_json_list(i.participants_json),
                "locations": _parse_json_list(i.locations_json),
                "evidence": _parse_json_list(i.evidence_json),
                "confidence": i.confidence,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
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
