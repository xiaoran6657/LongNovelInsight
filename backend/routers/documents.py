import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from db import get_session
from models.document import DocumentRead
from services import document_service

router = APIRouter(prefix="/topics/{topic_id}/documents", tags=["documents"])


class DocumentMetadataResponse(BaseModel):
    id: str
    topic_id: str
    original_filename: str
    file_type: str
    encoding: str
    file_size_bytes: int
    char_count: int
    status: str
    metadata: dict
    created_at: datetime
    updated_at: datetime


@router.post("/upload", status_code=201)
def upload(
    topic_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocumentRead:
    return document_service.upload_document(topic_id, file, session)


@router.get("/current")
def get_current(topic_id: str, session: Session = Depends(get_session)) -> DocumentRead:
    return document_service.get_current_document(topic_id, session)


@router.delete("/current")
def delete_current(topic_id: str, session: Session = Depends(get_session)) -> dict:
    return document_service.delete_current_document(topic_id, session)


@router.get("/current/metadata", response_model=DocumentMetadataResponse)
def get_document_metadata(
    topic_id: str, session: Session = Depends(get_session)
) -> DocumentMetadataResponse:
    doc = document_service.get_current_document(topic_id, session)
    metadata: dict = {}
    if doc.metadata_json:
        try:
            metadata = json.loads(doc.metadata_json)
        except json.JSONDecodeError:
            pass
    return DocumentMetadataResponse(
        id=doc.id,
        topic_id=doc.topic_id,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        encoding=doc.encoding,
        file_size_bytes=doc.file_size_bytes,
        char_count=doc.char_count,
        status=doc.status,
        metadata=metadata,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
