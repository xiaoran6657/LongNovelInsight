from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

import config
from models.document import Document, DocumentRead
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

    source_dir = storage.ensure_topic_dirs(topic_id)
    dest_path = source_dir / "original.txt"
    dest_path.write_text(text, encoding="utf-8")

    doc = Document(
        topic_id=topic_id,
        original_filename=file.filename,
        file_size_bytes=len(content),
        char_count=len(text),
        content_type=file.content_type,
        encoding=encoding,
        storage_path=str(dest_path.relative_to(config.DATA_DIR)),
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

    storage.safe_delete_file(config.DATA_DIR / doc.storage_path)
    storage.safe_delete_empty_dirs(storage.get_source_dir(topic_id))

    freed = topic.storage_bytes
    topic.storage_bytes = 0
    session.add(topic)

    session.delete(doc)
    session.commit()
    return {"deleted": True, "freed_bytes": freed}
