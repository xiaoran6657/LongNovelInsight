"""v0.4 Work CRUD API endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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


# ── Work-scoped document/parse endpoints ──

doc_router = APIRouter(prefix="/works/{work_id}", tags=["works"])


@doc_router.post("/documents/upload", status_code=201)
def upload_document_endpoint(
    work_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    from services.document_service import upload_document_to_work as svc_upload

    return svc_upload(work_id, file, session)


@doc_router.get("/documents/current")
def get_work_document(
    work_id: str, session: Session = Depends(get_session)
):
    from models.document import Document, DocumentRead

    doc = session.exec(
        select(Document).where(Document.work_id == work_id)
    ).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded to this Work")
    return DocumentRead.model_validate(doc)


@doc_router.post("/parse")
def parse_work(
    work_id: str,
    force: bool = False,
    session: Session = Depends(get_session),
):
    from services.parser_service import parse_novel_for_work

    try:
        return parse_novel_for_work(work_id, session, force=force)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@doc_router.get("/chapters")
def list_work_chapters(
    work_id: str, session: Session = Depends(get_session)
):
    from models.chapter import Chapter, ChapterRead
    from models.document import Document

    doc = session.exec(
        select(Document).where(Document.work_id == work_id)
    ).first()
    if doc is None:
        return {"chapters": []}

    chapters = session.exec(
        select(Chapter)
        .where(Chapter.document_id == doc.id)
        .order_by(Chapter.chapter_index)
    ).all()
    return {"chapters": [ChapterRead.model_validate(c).model_dump() for c in chapters]}


@doc_router.get("/chunks")
def list_work_chunks(
    work_id: str,
    include_text: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    from models.chunk import Chunk, ChunkRead
    from models.document import Document

    doc = session.exec(
        select(Document).where(Document.work_id == work_id)
    ).first()
    if doc is None:
        return {"chunks": []}

    chunks = session.exec(
        select(Chunk)
        .where(Chunk.document_id == doc.id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
        .offset(offset)
        .limit(limit)
    ).all()

    result = []
    for c in chunks:
        d = ChunkRead.model_validate(c).model_dump()
        if not include_text:
            d["text"] = ""
        result.append(d)

    return {"chunks": result}


@doc_router.get("/metadata")
def get_work_metadata(
    work_id: str, session: Session = Depends(get_session)
):
    import json

    from models.document import Document

    doc = session.exec(
        select(Document).where(Document.work_id == work_id)
    ).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No document found for this Work")

    metadata: dict = {}
    if doc.metadata_json:
        try:
            metadata = json.loads(doc.metadata_json)
        except json.JSONDecodeError:
            pass
    return {
        "id": doc.id,
        "topic_id": doc.topic_id,
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "encoding": doc.encoding,
        "file_size_bytes": doc.file_size_bytes,
        "char_count": doc.char_count,
        "status": doc.status,
        "metadata": metadata,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
