from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

import config
from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.chapter import Chapter
from models.chat import ChatMessage, ChatSession
from models.chunk import Chunk
from models.document import Document, DocumentRead
from models.extracted_atom import ExtractedAtom
from models.job import Job
from models.job_item import JobItem
from models.local_extraction import LocalExtraction
from models.topic import Topic
from services import storage

ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "gb2312",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
]


def _detect_encoding(content: bytes) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            text = content.decode(enc)
            return enc, text
        except (UnicodeDecodeError, LookupError):
            continue
    raise HTTPException(
        status_code=400,
        detail="Unsupported text encoding. Please upload UTF-8, GBK/GB18030, or UTF-16 txt.",
    )


def _get_doc_by_topic(topic_id: str, session: Session) -> Document | None:
    return session.exec(select(Document).where(Document.topic_id == topic_id)).first()


def _delete_document_derived_data(topic_id: str, session: Session) -> None:
    # Chat messages -> sessions
    sessions = session.exec(select(ChatSession).where(ChatSession.topic_id == topic_id)).all()
    for s in sessions:
        messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id)).all()
        for m in messages:
            session.delete(m)
        session.delete(s)

    # Analysis artifacts
    from services.artifact_storage_service import delete_artifacts_for_topic

    delete_artifacts_for_topic(session, topic_id)

    # Analysis outputs first (FK to analysis_run)
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    for o in outputs:
        session.delete(o)

    # v2 analysis artifacts: atoms → extractions → runs
    atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.topic_id == topic_id)).all()
    for a in atoms:
        session.delete(a)
    extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.topic_id == topic_id)
    ).all()
    for e in extractions:
        session.delete(e)
    runs = session.exec(select(AnalysisRun).where(AnalysisRun.topic_id == topic_id)).all()
    for r in runs:
        session.delete(r)

    # Jobs -> job_items
    jobs = session.exec(select(Job).where(Job.topic_id == topic_id)).all()
    for j in jobs:
        items = session.exec(select(JobItem).where(JobItem.job_id == j.id)).all()
        for ji in items:
            session.delete(ji)
        session.delete(j)

    # Chunks -> chapters
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
    for c in chunks:
        session.delete(c)
    chapters = session.exec(select(Chapter).where(Chapter.topic_id == topic_id)).all()
    for ch in chapters:
        session.delete(ch)


def upload_document(topic_id: str, file: UploadFile, session: Session) -> DocumentRead:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    existing = _get_doc_by_topic(topic_id, session)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Topic already has a document")

    content = file.file.read(config.UPLOAD_MAX_BYTES + 1)
    if len(content) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {config.UPLOAD_MAX_BYTES} bytes",
        )

    encoding, text = _detect_encoding(content)

    stripped = text.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail="Document contains no meaningful text content")

    source_dir = storage.ensure_topic_dirs(topic_id)
    dest_path = source_dir / "original.txt"
    dest_path.write_text(text, encoding="utf-8")

    try:
        rel_path = str(dest_path.resolve().relative_to(config.DATA_DIR.resolve()))
    except ValueError:
        raise HTTPException(status_code=500, detail="Failed to compute storage path")

    doc = Document(
        topic_id=topic_id,
        original_filename=file.filename,
        file_size_bytes=len(content),
        char_count=len(text),
        content_type=file.content_type,
        encoding=encoding,
        storage_path=rel_path,
    )
    session.add(doc)

    topic.storage_bytes = len(content)
    session.add(topic)

    session.commit()
    session.refresh(doc)
    return DocumentRead.model_validate(doc)


def get_current_document(topic_id: str, session: Session) -> DocumentRead:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    doc = _get_doc_by_topic(topic_id, session)
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded")

    return DocumentRead.model_validate(doc)


def delete_current_document(topic_id: str, session: Session) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    doc = _get_doc_by_topic(topic_id, session)
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded")

    # Delete derived data first (cascade)
    _delete_document_derived_data(topic_id, session)

    storage.safe_delete_file(config.DATA_DIR / doc.storage_path)
    storage.safe_delete_empty_dirs(storage.get_source_dir(topic_id))

    freed = topic.storage_bytes
    topic.storage_bytes = 0
    session.add(topic)

    session.delete(doc)
    session.commit()
    return {"deleted": True, "freed_bytes": freed}
