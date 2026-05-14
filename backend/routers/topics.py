from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models.document import Document
from models.model_provider import ModelProvider
from models.topic import Topic, TopicCreate, TopicRead
from services import topic_service

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("", status_code=201)
def create_topic(body: TopicCreate, session: Session = Depends(get_session)) -> TopicRead:
    if body.provider_id:
        provider = session.get(ModelProvider, body.provider_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Provider not found")

    topic = Topic(**body.model_dump())
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return TopicRead.model_validate(topic)


def _enrich_topic(t: Topic, session: Session) -> dict:
    doc = session.exec(select(Document).where(Document.topic_id == t.id)).first()
    doc_summary = topic_service.get_topic_document_summary(doc)
    analysis_summary = topic_service.get_topic_analysis_summary(t.id, session)
    return {
        **TopicRead.model_validate(t).model_dump(),
        "document": doc_summary,
        "analysis_summary": analysis_summary,
        "disk_usage_bytes": t.storage_bytes,
    }


@router.get("")
def list_topics(session: Session = Depends(get_session)) -> dict:
    topics = session.exec(select(Topic).order_by(Topic.created_at.desc())).all()
    return {"topics": [_enrich_topic(t, session) for t in topics]}


@router.get("/{topic_id}")
def get_topic(topic_id: str, session: Session = Depends(get_session)) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return _enrich_topic(topic, session)


@router.put("/{topic_id}/provider")
def bind_provider(
    topic_id: str,
    body: dict,
    session: Session = Depends(get_session),
) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    provider_id = body.get("provider_id") if body else None
    if not provider_id:
        raise HTTPException(status_code=422, detail="provider_id is required")

    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    topic.provider_id = provider_id
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return _enrich_topic(topic, session)


@router.delete("/{topic_id}")
def delete_topic(topic_id: str, session: Session = Depends(get_session)) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    result = topic_service.delete_topic(topic_id, session)
    if not result["deleted"]:
        raise HTTPException(status_code=500, detail="Failed to delete topic")
    return result
