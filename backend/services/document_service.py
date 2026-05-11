from fastapi import HTTPException, UploadFile
from sqlmodel import Session

import config
from models.document import Document, DocumentRead
from models.topic import Topic
from services import storage


def upload_document(topic_id: str, file: UploadFile, session: Session) -> DocumentRead:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    existing = session.get(Document, topic_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Topic already has a document")

    content = file.file.read(config.UPLOAD_MAX_BYTES + 1)
    if len(content) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {config.UPLOAD_MAX_BYTES} bytes",
        )

    encoding = "utf-8"
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="File encoding not supported. Only UTF-8 text files are accepted.",
            )

    source_dir = storage.ensure_topic_dirs(topic_id)
    dest_path = source_dir / "original.txt"
    dest_path.write_bytes(content)

    doc = Document(
        id=topic_id,
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

    doc = session.get(Document, topic_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No document uploaded")

    return DocumentRead.model_validate(doc)


def delete_current_document(topic_id: str, session: Session) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    doc = session.get(Document, topic_id)
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
