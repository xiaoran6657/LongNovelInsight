"""v0.4 Work CRUD API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models.document import Document
from models.topic import Topic
from models.work import Work, WorkCreate, WorkRead

topic_router = APIRouter(prefix="/topics/{topic_id}/works", tags=["works"])
work_router = APIRouter(prefix="/works", tags=["works"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _check_work(work_id: str, session: Session) -> Work:
    work = session.get(Work, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


def _has_data(work_id: str, session: Session) -> bool:
    """Check if a Work has any data — a Document alone is non-empty."""
    doc = session.exec(
        select(Document).where(Document.work_id == work_id)
    ).first()
    return doc is not None


# ── Topic-scoped endpoints ──


@topic_router.get("")
def list_works(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)

    # Backfill any legacy Documents without Work
    from services.work_service import backfill_null_work_ids

    backfill_null_work_ids(topic_id, session)

    works = session.exec(
        select(Work)
        .where(Work.topic_id == topic_id)
        .order_by(Work.series_index.is_(None), Work.series_index, Work.created_at)
    ).all()
    return {"works": [WorkRead.model_validate(w).model_dump() for w in works]}


@topic_router.post("", status_code=201)
def create_work(
    topic_id: str,
    body: WorkCreate,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    work = Work(topic_id=topic_id, **body.model_dump())
    session.add(work)
    session.commit()
    session.refresh(work)
    return WorkRead.model_validate(work).model_dump()


# ── Work-scoped endpoints ──


@work_router.get("/{work_id}")
def get_work(work_id: str, session: Session = Depends(get_session)) -> dict:
    work = _check_work(work_id, session)
    return WorkRead.model_validate(work).model_dump()


class WorkUpdateBody(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    series_index: int | None = None
    description: str | None = None


@work_router.patch("/{work_id}")
def update_work(
    work_id: str,
    body: WorkUpdateBody,
    session: Session = Depends(get_session),
) -> dict:
    work = _check_work(work_id, session)
    update = body.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(work, key, value)
    session.add(work)
    session.commit()
    session.refresh(work)
    return WorkRead.model_validate(work).model_dump()


@work_router.delete("/{work_id}")
def delete_work(work_id: str, session: Session = Depends(get_session)) -> dict:
    work = _check_work(work_id, session)

    if _has_data(work_id, session):
        raise HTTPException(
            status_code=409,
            detail=(
                "Deleting non-empty works is not supported in v0.4.0; "
                "remove the Topic or reset data manually."
            ),
        )

    session.delete(work)
    session.commit()
    return {"deleted": True}
