from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models.model_provider import ModelProvider
from models.topic import Topic, TopicCreate, TopicRead

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


@router.get("")
def list_topics(session: Session = Depends(get_session)) -> dict:
    topics = session.exec(select(Topic).order_by(Topic.created_at.desc())).all()
    return {
        "topics": [
            {
                **TopicRead.model_validate(t).model_dump(),
                "document": None,
                "analysis_summary": {},
                "disk_usage_bytes": t.storage_bytes,
            }
            for t in topics
        ]
    }


@router.get("/{topic_id}")
def get_topic(topic_id: str, session: Session = Depends(get_session)) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {
        **TopicRead.model_validate(topic).model_dump(),
        "document": None,
        "analysis_summary": {},
        "disk_usage_bytes": topic.storage_bytes,
    }


@router.delete("/{topic_id}")
def delete_topic(topic_id: str, session: Session = Depends(get_session)) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    freed_bytes = topic.storage_bytes
    session.delete(topic)
    session.commit()
    return {"deleted": True, "freed_bytes": freed_bytes}
