import io
import json
import zipfile

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


def _validate_epub_container(content: bytes, filename: str) -> None:
    """Validate that content is a well-formed EPUB container.

    Checks: valid zip, contains META-INF/container.xml.
    Does NOT parse OPF or extract text (that's Step 3).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "META-INF/container.xml" not in zf.namelist():
                raise HTTPException(
                    status_code=400,
                    detail=f"'{filename}' is not a valid EPUB: missing META-INF/container.xml",
                )
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail=f"'{filename}' is not a valid EPUB (not a zip file)",
        )


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


def _get_doc_by_work(work_id: str, session: Session) -> Document | None:
    return session.exec(select(Document).where(Document.work_id == work_id)).first()


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

    # FTS cleanup (virtual table, no FK cascade)
    from services.fts_service import delete_topic_chunk_fts

    delete_topic_chunk_fts(topic_id, session)


def upload_document(topic_id: str, file: UploadFile, session: Session) -> DocumentRead:
    """Legacy topic-level upload — resolves default Work and delegates."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    from services.work_service import ensure_default_work

    work = ensure_default_work(topic_id, session)

    # Check if Work already has a Document
    existing = _get_doc_by_work(work.id, session)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Work already has a document")

    return _do_upload(topic_id, work.id, work, file, session, topic)


def upload_document_to_work(work_id: str, file: UploadFile, session: Session) -> DocumentRead:
    """Upload a document into a specific Work. Rejects if Work already has a Document."""
    from models.work import Work as WorkModel

    work = session.get(WorkModel, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

    topic = session.get(Topic, work.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    existing = _get_doc_by_work(work_id, session)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Work already has a document")

    return _do_upload(work.topic_id, work_id, work, file, session, topic)


def _do_upload(
    topic_id: str,
    work_id: str,
    work,
    file: UploadFile,
    session: Session,
    topic: Topic,
) -> DocumentRead:
    """Shared upload logic — called by both topic-level and work-level uploads."""
    fn_lower = file.filename.lower() if file.filename else ""
    if fn_lower.endswith(".txt"):
        return _upload_txt(topic_id, work_id, file, session, topic, work)
    elif fn_lower.endswith(".epub"):
        return _upload_epub(topic_id, work_id, file, session, topic, work)
    else:
        raise HTTPException(status_code=400, detail="Only .txt and .epub files are supported")


def _upload_txt(
    topic_id: str, work_id: str, file: UploadFile, session: Session, topic, work
) -> DocumentRead:

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
        work_id=work_id,
        original_filename=file.filename,
        stored_filename="original.txt",
        file_type="txt",
        file_size_bytes=len(content),
        char_count=len(text),
        content_type=file.content_type,
        encoding=encoding,
        storage_path=rel_path,
        metadata_json=None,
    )
    session.add(doc)

    topic.storage_bytes = len(content)
    session.add(topic)
    _update_work_status(work, "uploaded", session)

    session.commit()
    session.refresh(doc)
    return DocumentRead.model_validate(doc)


def _upload_epub(
    topic_id: str, work_id: str, file: UploadFile, session: Session, topic, work
) -> DocumentRead:

    content = file.file.read(config.UPLOAD_MAX_BYTES + 1)
    if len(content) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {config.UPLOAD_MAX_BYTES} bytes",
        )

    _validate_epub_container(content, file.filename or "unknown.epub")

    source_dir = storage.ensure_topic_dirs(topic_id)
    dest_path = source_dir / "original.epub"
    dest_path.write_bytes(content)

    try:
        rel_path = str(dest_path.resolve().relative_to(config.DATA_DIR.resolve()))
    except ValueError:
        raise HTTPException(status_code=500, detail="Failed to compute storage path")

    metadata_json = json.dumps(
        {"source_format": "epub", "parsing_warnings": []}, ensure_ascii=False
    )

    doc = Document(
        topic_id=topic_id,
        work_id=work_id,
        original_filename=file.filename,
        stored_filename="original.epub",
        file_type="epub",
        file_size_bytes=len(content),
        char_count=0,  # set after parse
        content_type=file.content_type or "application/epub+zip",
        encoding="epub",
        storage_path=rel_path,
        metadata_json=metadata_json,
    )
    session.add(doc)

    topic.storage_bytes = len(content)
    session.add(topic)
    _update_work_status(work, "uploaded", session)

    session.commit()
    session.refresh(doc)
    return DocumentRead.model_validate(doc)


def get_current_document(topic_id: str, session: Session) -> DocumentRead:
    """Legacy topic-level get — resolves default Work."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    from services.work_service import get_or_create_default_work

    try:
        work = get_or_create_default_work(topic_id, session)
    except HTTPException:
        raise HTTPException(status_code=404, detail="No document uploaded")

    doc = _get_doc_by_work(work.id, session)
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded")

    return DocumentRead.model_validate(doc)


def delete_current_document(topic_id: str, session: Session) -> dict:
    """Legacy topic-level delete — resolves default Work."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    from services.work_service import get_or_create_default_work

    try:
        work = get_or_create_default_work(topic_id, session)
    except HTTPException:
        raise HTTPException(status_code=404, detail="No document uploaded")

    doc = _get_doc_by_work(work.id, session)
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


def _update_work_status(work, status: str, session: Session) -> None:
    """Update Work status if it's a progression (empty→uploaded→parsed)."""
    progression = {"empty": 0, "uploaded": 1, "parsed": 2, "analyzed": 3}
    if progression.get(status, 0) > progression.get(work.status, -1):
        work.status = status
        session.add(work)
