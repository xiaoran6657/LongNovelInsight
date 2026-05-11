from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from db import get_session
from models.document import DocumentRead
from services import document_service

router = APIRouter(prefix="/topics/{topic_id}/documents", tags=["documents"])


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
