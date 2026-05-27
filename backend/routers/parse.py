from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

import config
from db import get_session
from models.analysis_output import AnalysisOutput
from models.chapter import Chapter, ChapterRead
from models.chunk import Chunk, ChunkRead
from models.document import Document
from models.topic import Topic
from services import parser_service, storage

router = APIRouter(prefix="/topics/{topic_id}", tags=["parse"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _check_document(topic_id: str, session: Session) -> Document:
    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded")
    return doc


@router.post("/parse")
def parse(
    topic_id: str,
    force: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    doc = _check_document(topic_id, session)

    # Validate source file exists (format-aware path)
    source_path = storage.get_source_file_path(topic_id, doc.stored_filename)
    if not source_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Source file not found on disk: {doc.stored_filename}",
        )

    try:
        result = parser_service.parse_novel(topic_id, session, force=force)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return result


@router.get("/chapters")
def list_chapters(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    chapters = session.exec(
        select(Chapter).where(Chapter.topic_id == topic_id).order_by(Chapter.chapter_index)
    ).all()
    return {"chapters": [ChapterRead.model_validate(c).model_dump() for c in chapters]}


@router.get("/chunks")
def list_chunks(
    topic_id: str,
    include_text: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
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


@router.get("/chunks/meta")
def get_chunks_meta(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    _check_document(topic_id, session)

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None or doc.status != "parsed":
        raise HTTPException(status_code=409, detail="Document is not parsed")

    from services.analysis_selection_service import get_chunks_meta as svc_meta

    meta = svc_meta(session, topic_id)
    if meta["chunk_count"] == 0:
        raise HTTPException(status_code=409, detail="No chunks found; parse document first")
    return meta


@router.get("/storage")
def get_storage(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)

    db_size = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    data_size = storage.compute_data_dir_size()

    topic = session.get(Topic, topic_id)
    topic_doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()

    # Real chunk text bytes (stored in DB, estimate from char_count)
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
    chunks_size_bytes = sum(len(c.text.encode("utf-8")) for c in chunks)

    # Real analysis JSON bytes (stored in DB)
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    analyses_size_bytes = sum(len(o.content_json.encode("utf-8")) for o in outputs)

    novel_size = topic_doc.file_size_bytes if topic_doc else 0
    total_bytes = novel_size + chunks_size_bytes + analyses_size_bytes

    return {
        "total_disk_usage_bytes": db_size + data_size,
        "database_size_bytes": db_size,
        "data_dir_size_bytes": data_size,
        "topics": [
            {
                "topic_id": topic.id if topic else topic_id,
                "topic_name": topic.name if topic else "",
                "novel_size_bytes": novel_size,
                "chunks_size_bytes": chunks_size_bytes,
                "analyses_size_bytes": analyses_size_bytes,
                "total_bytes": total_bytes,
            }
        ],
    }
