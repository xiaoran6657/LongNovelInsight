from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.chat import (
    ChatAnswerRead,
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
)
from models.topic import Topic
from services import chat_service

topic_router = APIRouter(prefix="/topics/{topic_id}/chat", tags=["chat"])
session_router = APIRouter(prefix="/chat/sessions", tags=["chat"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@topic_router.post("/sessions", status_code=201)
def create_session(
    topic_id: str,
    body: ChatSessionCreate,
    session: Session = Depends(get_session),
) -> ChatSessionRead:
    _check_topic(topic_id, session)
    s = chat_service.create_chat_session(topic_id, body.title, session)
    return ChatSessionRead.model_validate(s)


@topic_router.get("/sessions")
def list_sessions(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    sessions = chat_service.list_chat_sessions(topic_id, session)
    return {"sessions": [ChatSessionRead.model_validate(s).model_dump() for s in sessions]}


@session_router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    session: Session = Depends(get_session),
) -> dict:
    s = chat_service.get_chat_session(session_id, session)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = chat_service.get_chat_messages(session_id, session)
    return {
        "messages": [ChatMessageRead.model_validate(m).model_dump() for m in messages],
        "total": len(messages),
    }


@session_router.post("/{session_id}/messages")
def send_message(
    session_id: str,
    body: dict,
    session: Session = Depends(get_session),
) -> ChatAnswerRead:
    s = chat_service.get_chat_session(session_id, session)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        msg = ChatMessageCreate.parse_and_validate(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    work_ids = body.get("work_ids") if isinstance(body, dict) else None

    try:
        assistant_msg = chat_service.send_user_message(
            session_id, msg.content, session, work_ids=work_ids
        )
    except ValueError as e:
        msg_str = str(e)
        if "no provider" in msg_str.lower():
            raise HTTPException(status_code=409, detail=msg_str)
        raise HTTPException(status_code=400, detail=msg_str)

    return ChatAnswerRead.from_message(assistant_msg)


@session_router.delete("/{session_id}")
def delete_session(
    session_id: str,
    session: Session = Depends(get_session),
) -> dict:
    ok = chat_service.delete_chat_session(session_id, session)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


@session_router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    session: Session = Depends(get_session),
) -> dict:
    ok = chat_service.delete_chat_message(message_id, session)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"deleted": True}
