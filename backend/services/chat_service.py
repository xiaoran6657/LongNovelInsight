import json
import logging

from sqlmodel import Session, select

from models.chat import ChatMessage, ChatSession
from models.model_provider import ModelProvider, mask_api_key
from models.topic import Topic
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.retrieval_service import build_evidence_context

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are a novel analysis assistant. "
    "Answer questions about the novel based on the provided evidence context.\n\n"
    "Rules:\n"
    "1. Base your answer on the evidence chunks and analysis outputs provided.\n"
    "2. If evidence is insufficient, state that clearly in the uncertainty field.\n"
    "3. Do NOT fabricate information not present in the evidence.\n"
    "4. Reference specific chunks or analysis outputs when possible.\n\n"
    "Your response MUST be valid JSON:\n"
    '{"answer": "string", "evidence": ["string"], "uncertainty": "string or null"}'
)


def create_chat_session(topic_id: str, title: str, session: Session) -> ChatSession:
    s = ChatSession(topic_id=topic_id, title=title)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def list_chat_sessions(topic_id: str, session: Session) -> list[ChatSession]:
    return list(
        session.exec(
            select(ChatSession)
            .where(ChatSession.topic_id == topic_id)
            .order_by(ChatSession.created_at.desc())
        ).all()
    )


def get_chat_session(session_id: str, session: Session) -> ChatSession | None:
    return session.get(ChatSession, session_id)


def get_chat_messages(session_id: str, session: Session) -> list[ChatMessage]:
    return list(
        session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).all()
    )


def delete_chat_session(session_id: str, session: Session) -> bool:
    s = session.get(ChatSession, session_id)
    if s is None:
        return False
    messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
    for m in messages:
        session.delete(m)
    session.delete(s)
    session.commit()
    return True


def _select_provider(topic: Topic, session: Session) -> ModelProvider:
    if topic.provider_id:
        provider = session.get(ModelProvider, topic.provider_id)
        if provider is not None:
            return provider
    provider = session.exec(
        select(ModelProvider).where(ModelProvider.is_default == True)  # noqa: E712
    ).first()
    if provider is None:
        raise ValueError("No provider configured")
    return provider


def send_user_message(session_id: str, content: str, session: Session) -> ChatMessage:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise ValueError("Chat session not found")

    # Save user message
    user_msg = ChatMessage(session_id=session_id, role="user", content=content)
    session.add(user_msg)
    session.flush()

    # Get topic
    topic = session.get(Topic, chat_session.topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    # Select provider
    provider = _select_provider(topic, session)

    # Retrieve evidence
    evidence = build_evidence_context(topic.id, content, session)

    # Build evidence text
    evidence_parts = []
    for c in evidence.get("chunks", []):
        evidence_parts.append(
            f"[Chunk {c['chunk_id']} ch{c['chapter_index']}/"
            f"c{c['chunk_index']}]: {c['text_excerpt']}"
        )
    for a in evidence.get("analysis_outputs", []):
        evidence_parts.append(
            f"[Analysis {a['output_id']} {a['output_type']}]: {a['content_excerpt']}"
        )
    evidence_text = "\n\n".join(evidence_parts) if evidence_parts else "(no evidence found)"

    # Build messages for LLM
    system_msg = LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT)
    context_msg = LLMMessage(
        role="user",
        content=f"Evidence context:\n{evidence_text}\n\nUser question: {content}",
    )

    client = OpenAICompatibleLLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
    )

    try:
        response = client.chat(
            messages=[system_msg, context_msg],
            model=provider.model_name,
            temperature=provider.temperature,
            max_tokens=provider.max_output_tokens,
            response_format={"type": "json_object"},
        )
    except LLMClientError as e:
        logger.error(
            "LLM call failed for chat: %s",
            e.message.replace(provider.api_key, mask_api_key(provider.api_key)),
        )
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="Sorry, I encountered an error processing your question.",
            evidence_json=None,
            uncertainty="LLM error",
        )
        session.add(assistant_msg)
        session.commit()
        session.refresh(assistant_msg)
        return assistant_msg

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        logger.error("Invalid JSON from LLM for chat")
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=response.content,
            evidence_json=None,
            uncertainty="LLM response was not valid JSON",
        )
        session.add(assistant_msg)
        session.commit()
        session.refresh(assistant_msg)
        return assistant_msg

    answer = parsed.get("answer", response.content)
    evidence_list = parsed.get("evidence", [])
    uncertainty = parsed.get("uncertainty")

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        evidence_json=json.dumps(evidence_list, ensure_ascii=False) if evidence_list else None,
        uncertainty=uncertainty,
    )
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)
    return assistant_msg
