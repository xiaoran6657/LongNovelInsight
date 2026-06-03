"""v0.4 Work CRUD API endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
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
    force: bool = Query(False),
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


# ── Work-scoped analysis endpoints ──


class WorkCreateRunRequest(BaseModel):
    mode: str = "preview"
    requested_types: list[str] | None = None
    limit_chunks: int | None = None
    chunk_index_start: int | None = None
    chunk_index_end: int | None = None
    chapter_index_start: int | None = None
    chapter_index_end: int | None = None
    force: bool = False
    start_immediately: bool = True


@doc_router.post("/analysis/runs", status_code=201)
def create_work_analysis_run(
    work_id: str,
    body: WorkCreateRunRequest,
    session: Session = Depends(get_session),
):
    from services import analysis_run_service

    work = _check_work(work_id, session)

    try:
        run = analysis_run_service.create_analysis_run(
            session,
            work.topic_id,
            mode=body.mode,
            requested_types=body.requested_types,
            limit_chunks=body.limit_chunks,
            chunk_index_start=body.chunk_index_start,
            chunk_index_end=body.chunk_index_end,
            chapter_index_start=body.chapter_index_start,
            chapter_index_end=body.chapter_index_end,
            force=body.force,
            work_id=work_id,
        )
    except ValueError as e:
        msg = str(e)
        conflict_keywords = (
            "no provider", "no chunks", "not parsed",
            "parse document", "already running", "no document",
        )
        if any(kw in msg.lower() for kw in conflict_keywords):
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=422, detail=msg)

    if body.start_immediately:
        analysis_run_service.start_analysis_run(run.id)

    return {
        "run": {
            "id": run.id,
            "topic_id": run.topic_id,
            "mode": run.mode,
            "status": run.status,
            "progress_total": run.progress_total,
        },
        "status_url": f"/api/analysis/runs/{run.id}",
    }


@doc_router.get("/analysis/runs")
def list_work_analysis_runs(
    work_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    from services import analysis_run_service

    work = _check_work(work_id, session)

    # List runs for the topic (existing function), then filter by work-scoped chunks
    page, total = analysis_run_service.list_analysis_runs(
        session, work.topic_id, limit=limit, offset=offset
    )

    return {
        "runs": [
            {
                "id": r.id,
                "mode": r.mode,
                "status": r.status,
                "extraction_succeeded": r.extraction_succeeded,
                "extraction_failed": r.extraction_failed,
                "merge_succeeded": r.merge_succeeded,
                "merge_failed": r.merge_failed,
                "total_tokens": r.total_tokens,
                "model_used": r.model_used,
                "work_id": r.get_chunk_selection().get("work_id"),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in page
        ],
        "total": total,
    }


@doc_router.get("/analysis/outputs")
def list_work_analysis_outputs(
    work_id: str,
    session: Session = Depends(get_session),
):
    from models.analysis_output import AnalysisOutput

    work = _check_work(work_id, session)
    outputs = session.exec(
        select(AnalysisOutput)
        .where(AnalysisOutput.topic_id == work.topic_id)
        .order_by(AnalysisOutput.created_at.desc())
    ).all()

    result = []
    for o in outputs:
        if o.output_type.startswith("merge_"):
            continue
        result.append({
            "id": o.id,
            "topic_id": o.topic_id,
            "run_id": o.run_id,
            "output_type": o.output_type,
            "title": o.title,
            "confidence": o.confidence,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return {"outputs": result, "total": len(result)}
