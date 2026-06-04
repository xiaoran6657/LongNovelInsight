"""Work CRUD and default Work resolution helpers."""

from fastapi import HTTPException
from sqlmodel import Session, select

from models.document import Document
from models.topic import Topic
from models.work import Work


def get_or_create_default_work(topic_id: str, session: Session) -> Work:
    """Get the default Work for a Topic, creating one if a legacy Document exists.

    Resolution order:
    1. Existing Work with series_index=1 for this topic.
    2. Oldest Work (by created_at) for this topic.
    3. If no Work exists but a legacy Document exists: create a default Work
       and backfill document.work_id.
    4. If no Work and no Document: raise 404.

    Idempotent — safe to call multiple times.
    """
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Prefer series_index=1, fallback to oldest
    work = session.exec(
        select(Work)
        .where(Work.topic_id == topic_id)
        .order_by(Work.series_index.is_(None), Work.series_index, Work.created_at)
    ).first()

    if work is not None:
        # Backfill any NULL-work_id Documents to this Work
        orphan_docs = session.exec(
            select(Document).where(
                Document.topic_id == topic_id,
                Document.work_id.is_(None),  # type: ignore[arg-type]
            )
        ).all()
        if orphan_docs:
            for d in orphan_docs:
                d.work_id = work.id
                session.add(d)
            session.commit()
        return work

    # No Work exists — check for legacy Document
    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()

    if doc is None:
        raise HTTPException(status_code=404, detail="No Work or Document found for this Topic")

    title = _derive_work_title(doc)
    work = Work(
        topic_id=topic_id,
        title=title,
        series_index=1,
        status=_derive_work_status(doc),
    )
    session.add(work)
    session.flush()

    doc.work_id = work.id
    session.add(doc)
    session.commit()
    session.refresh(work)
    return work


def ensure_default_work(topic_id: str, session: Session) -> Work:
    """Get or create a default Work for a Topic. Unlike get_or_create_default_work,
    this creates a Work even if no Document exists yet (for pre-upload resolution).
    """
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    work = session.exec(
        select(Work)
        .where(Work.topic_id == topic_id)
        .order_by(Work.series_index.is_(None), Work.series_index, Work.created_at)
    ).first()

    if work is not None:
        return work

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()

    title = _derive_work_title(doc) if doc else topic.name
    work = Work(
        topic_id=topic_id,
        title=title,
        series_index=1,
        status=_derive_work_status(doc) if doc else "empty",
    )
    session.add(work)
    session.commit()
    session.refresh(work)
    return work


def backfill_null_work_ids(topic_id: str, session: Session) -> int:
    """Attach all Documents with work_id=NULL to a default Work.

    Returns count of documents backfilled.
    """
    docs = session.exec(
        select(Document).where(
            Document.topic_id == topic_id,
            Document.work_id.is_(None),  # type: ignore[arg-type]
        )
    ).all()

    if not docs:
        return 0

    work = _find_or_create_work_for_topic(topic_id, docs[0], session)
    count = 0
    for doc in docs:
        if doc.work_id is None:
            doc.work_id = work.id
            session.add(doc)
            count += 1

    if count > 0:
        session.commit()
    return count


def backfill_all_null_work_ids(session: Session) -> int:
    """Attach ALL Documents with work_id=NULL across all Topics to default Works.

    Used by migration after schema changes. Returns total count.
    """
    docs = session.exec(
        select(Document).where(Document.work_id.is_(None))  # type: ignore[arg-type]
    ).all()

    if not docs:
        return 0

    count = 0
    for doc in docs:
        work = _find_or_create_work_for_topic(doc.topic_id, doc, session)
        doc.work_id = work.id
        session.add(doc)
        count += 1

    if count > 0:
        session.commit()
    return count


def _find_or_create_work_for_topic(topic_id: str, doc: Document, session: Session) -> Work:
    """Find existing Work for topic or create a default one."""
    work = session.exec(
        select(Work)
        .where(Work.topic_id == topic_id)
        .order_by(Work.series_index.is_(None), Work.series_index, Work.created_at)
    ).first()

    if work is not None:
        return work

    title = _derive_work_title(doc)
    work = Work(
        topic_id=topic_id,
        title=title,
        series_index=1,
        status=_derive_work_status(doc),
    )
    session.add(work)
    session.flush()
    return work


def _derive_work_title(doc: Document) -> str:
    title = doc.original_filename
    if title.endswith(".txt") or title.endswith(".epub"):
        title = title.rsplit(".", 1)[0]
    return title


def _derive_work_status(doc: Document) -> str:
    return doc.status if doc.status != "uploaded" else "uploaded"
