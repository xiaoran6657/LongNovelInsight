import json
import logging
from collections.abc import Callable

from sqlalchemy import case, func, update
from sqlmodel import Session, select

from models.chat import ChatMessage, ChatSession
from models.model_provider import ModelProvider, mask_api_key
from models.retrieval_trace import RetrievalTrace
from models.topic import Topic
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.retrieval_service import (
    DEFAULT_TOP_K,
    hybrid_retrieve,
    retrieve_analysis,
    retrieve_chunks,
    save_retrieval_trace,
)

logger = logging.getLogger(__name__)

_ROLE_ORDER = case((ChatMessage.role == "user", 0), (ChatMessage.role == "assistant", 1), else_=2)

CHAT_SYSTEM_PROMPT = (
    "You are a novel analysis assistant. "
    "Answer questions about the novel based on the provided evidence context.\n\n"
    "Rules:\n"
    "1. Base your answer on the evidence chunks and analysis outputs provided.\n"
    "2. If evidence is insufficient, state that clearly in the uncertainty field.\n"
    "3. Do NOT fabricate information not present in the evidence.\n"
    "4. Reference specific chunks or analysis outputs when possible.\n"
    "5. Conversation history may be used only to resolve references such "
    'as "he", "she", "this event"; factual claims must still be grounded '
    "in the evidence context.\n\n"
    "Your response MUST be valid JSON:\n"
    '{"answer": "string", "evidence": ["string"], "uncertainty": "string or null"}'
)

HISTORY_MESSAGE_LIMIT = 6


class ChatResendConflictError(Exception):
    pass


class ChatResendGenerationError(Exception):
    pass


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
            .order_by(
                ChatMessage.sequence_index.is_(None),
                ChatMessage.sequence_index,
                _ROLE_ORDER,
                ChatMessage.created_at,
                ChatMessage.id,
            )
        ).all()
    )


def _following_assistant(msg: ChatMessage, session: Session) -> ChatMessage | None:
    linked = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == msg.session_id)
        .where(ChatMessage.reply_to_message_id == msg.id)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.sequence_index, ChatMessage.id)
    ).first()
    if linked is not None:
        return linked
    if msg.sequence_index is not None:
        return None
    next_msgs = list(
        session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == msg.session_id)
            .where(ChatMessage.created_at > msg.created_at)
            .order_by(ChatMessage.created_at, ChatMessage.id)
            .limit(1)
        ).all()
    )
    if next_msgs and next_msgs[0].role == "assistant":
        return next_msgs[0]
    return None


def _delete_chat_message_records(msg: ChatMessage, session: Session) -> None:
    assistant = _following_assistant(msg, session) if msg.role == "user" else None
    message_ids = [msg.id]
    if assistant is not None:
        message_ids.append(assistant.id)
    traces = session.exec(
        select(RetrievalTrace).where(RetrievalTrace.message_id.in_(message_ids))  # noqa: E711
    ).all()
    for trace in traces:
        session.delete(trace)
    session.flush()
    if assistant is not None:
        session.delete(assistant)
    session.delete(msg)


def delete_chat_message(message_id: str, session: Session) -> bool:
    """Delete a user message and the assistant response immediately after it."""
    msg = session.get(ChatMessage, message_id)
    if msg is None:
        return False
    _delete_chat_message_records(msg, session)
    session.commit()
    return True


def delete_chat_session(session_id: str, session: Session) -> bool:
    s = session.get(ChatSession, session_id)
    if s is None:
        return False
    traces = session.exec(
        select(RetrievalTrace).where(RetrievalTrace.session_id == session_id)
    ).all()
    for trace in traces:
        session.delete(trace)
    session.flush()
    messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
    for m in messages:
        session.delete(m)
    session.flush()
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


def _build_recent_history_messages(
    session_id: str,
    session: Session,
    limit: int = HISTORY_MESSAGE_LIMIT,
    exclude_message_ids: set[str] | None = None,
) -> list[LLMMessage]:
    statement = select(ChatMessage).where(ChatMessage.session_id == session_id)
    if exclude_message_ids:
        statement = statement.where(ChatMessage.id.not_in(exclude_message_ids))
    messages = list(
        session.exec(
            statement.order_by(
                ChatMessage.sequence_index.is_(None),
                ChatMessage.sequence_index.desc(),
                _ROLE_ORDER.desc(),
                ChatMessage.created_at.desc(),
                ChatMessage.id.desc(),
            ).limit(limit)
        ).all()
    )
    messages.reverse()  # chronological order
    result = []
    for m in messages:
        if m.role in ("user", "assistant"):
            result.append(LLMMessage(role=m.role, content=m.content))
    return result


def _sanitize_answer(parsed: dict, fallback: str) -> str:
    answer = parsed.get("answer", fallback)
    if not isinstance(answer, str):
        answer = str(answer)
    return answer if answer.strip() else fallback


def _sanitize_evidence(parsed: dict) -> list[str]:
    evidence = parsed.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    return [str(e) for e in evidence if isinstance(e, str)]


def _sanitize_uncertainty(parsed: dict) -> str | None:
    uncertainty = parsed.get("uncertainty")
    if uncertainty is None:
        return None
    if not isinstance(uncertainty, str):
        return str(uncertainty)
    return uncertainty


def _build_structured_evidence(candidates: list[dict]) -> list[dict]:
    """Convert retrieval candidates to structured evidence items for storage."""
    return [
        {
            "text": c.get("snippet", ""),
            "source_type": c["source_type"],
            "source_id": c["source_id"],
            "chunk_id": c.get("chunk_id"),
            "title": c.get("title", ""),
            "method": c["method"],
            "score": c["score"],
            "locator": c.get("source_locator"),
            "work_id": c.get("work_id"),
            "work_title": c.get("work_title"),
            "series_index": c.get("series_index"),
        }
        for c in candidates
    ]


def _annotate_candidates_work_meta(candidates: list[dict], session: Session) -> None:
    """Annotate candidates with work_id/work_title from chunk → document → work."""
    from models.chunk import Chunk as ChunkModel
    from models.document import Document as DocumentModel
    from models.work import Work as WorkModel

    for c in candidates:
        cid = c.get("chunk_id")
        if not cid:
            continue
        chunk = session.get(ChunkModel, cid)
        if chunk is None:
            continue
        doc = session.get(DocumentModel, chunk.document_id)
        if doc is not None and doc.work_id:
            c["work_id"] = doc.work_id
            work = session.get(WorkModel, doc.work_id)
            if work is not None:
                c["work_title"] = work.title
                c["series_index"] = work.series_index


def send_user_message(
    session_id: str,
    content: str,
    session: Session,
    work_ids: list[str] | None = None,
    *,
    commit: bool = True,
    history_excluded_message_ids: set[str] | None = None,
    before_deferred_write: Callable[[], None] | None = None,
    turn_id: str | None = None,
    sequence_start: int | None = None,
) -> ChatMessage:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise ValueError("Chat session not found")

    trimmed = content.strip()
    if not trimmed:
        raise ValueError("Message content is empty")

    # Normal sends preserve the existing trace-before-LLM behavior. Atomic resend
    # generation defers every write until the LLM result is available.
    if sequence_start is None:
        # SQLite serializes this no-op write. Once it completes, the following
        # max() observes every earlier committed turn before reserving the next.
        session.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(title=ChatSession.title)
        )
        sequence_start = (
            session.exec(
                select(func.max(ChatMessage.sequence_index)).where(
                    ChatMessage.session_id == session_id
                )
            ).one()
            or 0
        ) + 1
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=trimmed,
        turn_id=turn_id,
        sequence_index=sequence_start,
    )
    user_msg.turn_id = user_msg.turn_id or user_msg.id
    if commit:
        session.add(user_msg)
        session.flush()

    # Get topic
    topic = session.get(Topic, chat_session.topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    # Select provider
    provider = _select_provider(topic, session)

    # ── v0.3: Hybrid retrieval instead of legacy keyword-only ──
    fetch_k = max(DEFAULT_TOP_K * 3, DEFAULT_TOP_K + 30) if work_ids else DEFAULT_TOP_K
    candidates = hybrid_retrieve(
        topic_id=topic.id,
        query=trimmed,
        session=session,
        top_k=fetch_k,
    )
    # Annotate and filter by work_ids
    _annotate_candidates_work_meta(candidates, session)
    if work_ids:
        candidates = [c for c in candidates if c.get("work_id") in work_ids]

    # Fall back to legacy fuzzy scoring when hybrid returns nothing
    # (hybrid is precise; long natural-language CJK queries may need fuzzier matching)
    if not candidates:
        legacy_chunks = retrieve_chunks(topic.id, trimmed, session, DEFAULT_TOP_K)
        legacy_analysis = retrieve_analysis(topic.id, trimmed, session, DEFAULT_TOP_K)
        for c in legacy_chunks:
            candidates.append(
                {
                    "source_type": "chunk",
                    "source_id": c["chunk_id"],
                    "chunk_id": c["chunk_id"],
                    "chapter_index": c.get("chapter_index"),
                    "chunk_index": c.get("chunk_index"),
                    "title": "",
                    "snippet": c.get("text_excerpt", ""),
                    "score": float(c.get("score", 0)),
                    "method": "legacy",
                    "matched_terms": [],
                    "source_locator": None,
                }
            )
        for a in legacy_analysis:
            candidates.append(
                {
                    "source_type": "analysis_output",
                    "source_id": a["output_id"],
                    "chunk_id": None,
                    "chapter_index": None,
                    "chunk_index": None,
                    "title": a.get("title", ""),
                    "snippet": a.get("content_excerpt", ""),
                    "score": float(a.get("score", 0)),
                    "method": "legacy",
                    "matched_terms": [],
                    "source_locator": None,
                }
            )
        # Annotate and filter legacy candidates by work_ids
        _annotate_candidates_work_meta(candidates, session)
        if work_ids:
            candidates = [c for c in candidates if c.get("work_id") in work_ids]
        candidates.sort(key=lambda x: x["score"], reverse=True)
        candidates = candidates[:DEFAULT_TOP_K]
        # Normalize legacy raw scores to [0, 1] so chat evidence_json
        # is consistent with hybrid retrieval score semantics.
        if candidates:
            scores = [c["score"] for c in candidates]
            min_s, max_s = min(scores), max(scores)
            if max_s != min_s:
                for c in candidates:
                    c["score"] = round((c["score"] - min_s) / (max_s - min_s), 4)
            elif max_s > 0:
                for c in candidates:
                    c["score"] = 1.0

    # Build evidence text for LLM from unified candidates
    evidence_parts = []
    for c in candidates:
        evidence_parts.append(
            f"[{c['source_type'].upper()} {c['source_id']} "
            f"method={c['method']} score={c['score']:.2f}]: {c['snippet']}"
        )
    evidence_text = "\n\n".join(evidence_parts) if evidence_parts else "(no evidence found)"

    # Persist RetrievalTrace for every retrieval attempt, before the LLM call,
    # so error paths (LLM failure, invalid JSON) still have a trace.
    if commit:
        save_retrieval_trace(
            topic_id=topic.id,
            query=trimmed,
            results=list(candidates),
            session=session,
            session_id=session_id,
            message_id=user_msg.id,
            method="hybrid",
            work_ids=work_ids,
        )

    # When no evidence was found, skip the LLM call entirely and return
    # a conservative answer. This prevents the LLM from fabricating
    # confident-sounding content with no grounding.
    if not candidates:
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="No evidence was found in the novel to answer this question.",
            evidence_json=None,
            uncertainty="No evidence found in the novel text",
        )
        if not commit:
            session.rollback()
        return _finish_chat_turn(
            assistant_msg,
            user_msg,
            topic.id,
            trimmed,
            candidates,
            session,
            work_ids,
            commit,
            before_deferred_write,
        )

    # Build recent history for multi-turn context
    history_messages = _build_recent_history_messages(
        session_id,
        session,
        exclude_message_ids=history_excluded_message_ids,
    )

    # Build messages for LLM
    system_msg = LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT)
    context_msg = LLMMessage(
        role="user",
        content=f"Evidence context:\n{evidence_text}\n\nCurrent user question: {trimmed}",
    )

    messages = [system_msg] + history_messages + [context_msg]

    provider_base_url = provider.base_url
    provider_api_key = provider.api_key
    provider_model = provider.model_name
    provider_temperature = provider.temperature
    provider_max_tokens = provider.max_output_tokens
    if not commit:
        session.rollback()

    client = OpenAICompatibleLLMClient(
        base_url=provider_base_url,
        api_key=provider_api_key,
    )

    try:
        response = client.chat(
            messages=messages,
            model=provider_model,
            temperature=provider_temperature,
            max_tokens=provider_max_tokens,
            response_format={"type": "json_object"},
        )
        usage = response.usage or {}
        model_used = response.model or provider_model
    except LLMClientError as e:
        logger.error(
            "LLM call failed for chat: %s",
            e.message.replace(provider_api_key, mask_api_key(provider_api_key)),
        )
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="Sorry, I encountered an error processing your question.",
            evidence_json=None,
            uncertainty="LLM error",
        )
        return _finish_chat_turn(
            assistant_msg,
            user_msg,
            topic.id,
            trimmed,
            candidates,
            session,
            work_ids,
            commit,
            before_deferred_write,
        )

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
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model_used=model_used,
        )
        return _finish_chat_turn(
            assistant_msg,
            user_msg,
            topic.id,
            trimmed,
            candidates,
            session,
            work_ids,
            commit,
            before_deferred_write,
        )

    answer = _sanitize_answer(parsed, response.content)
    uncertainty = _sanitize_uncertainty(parsed)

    # At this point candidates is always non-empty (empty case returns early above).

    structured_evidence = _build_structured_evidence(candidates)

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        evidence_json=json.dumps(structured_evidence, ensure_ascii=False),
        uncertainty=uncertainty,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        model_used=model_used,
    )
    return _finish_chat_turn(
        assistant_msg,
        user_msg,
        topic.id,
        trimmed,
        candidates,
        session,
        work_ids,
        commit,
        before_deferred_write,
    )


def _persist_assistant_message(
    assistant_msg: ChatMessage, session: Session, commit: bool
) -> ChatMessage:
    session.add(assistant_msg)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(assistant_msg)
    return assistant_msg


def _finish_chat_turn(
    assistant_msg: ChatMessage,
    user_msg: ChatMessage,
    topic_id: str,
    query: str,
    candidates: list[dict],
    session: Session,
    work_ids: list[str] | None,
    commit: bool,
    before_deferred_write: Callable[[], None] | None,
) -> ChatMessage:
    assistant_msg.turn_id = user_msg.turn_id
    assistant_msg.reply_to_message_id = user_msg.id
    assistant_msg.sequence_index = user_msg.sequence_index
    if not commit:
        if before_deferred_write is not None:
            before_deferred_write()
        session.add(user_msg)
        session.flush()
        save_retrieval_trace(
            topic_id=topic_id,
            query=query,
            results=list(candidates),
            session=session,
            session_id=user_msg.session_id,
            message_id=user_msg.id,
            method="hybrid",
            work_ids=work_ids,
            commit=False,
        )
    return _persist_assistant_message(assistant_msg, session, commit)


def resend_user_message(
    session_id: str,
    message_id: str,
    content: str,
    session: Session,
    expected_assistant_message_id: str,
    work_ids: list[str] | None = None,
) -> ChatMessage:
    original, original_assistant = _validate_resend_target(
        session_id, message_id, expected_assistant_message_id, session
    )
    excluded_ids = {original.id, original_assistant.id}
    replacement_original: ChatMessage | None = None

    def lock_and_revalidate() -> None:
        nonlocal replacement_original
        locked = session.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.role == "user")
            .values(content=ChatMessage.content)
        )
        if locked.rowcount != 1:
            raise ChatResendConflictError(
                "The original message pair has changed; refresh and try again"
            )
        replacement_original, _ = _validate_resend_target(
            session_id,
            message_id,
            expected_assistant_message_id,
            session,
            populate_existing=True,
        )

    try:
        revised_assistant = send_user_message(
            session_id,
            content,
            session,
            work_ids=work_ids,
            commit=False,
            history_excluded_message_ids=excluded_ids,
            before_deferred_write=lock_and_revalidate,
            turn_id=original.turn_id or original.id,
            sequence_start=original.sequence_index,
        )
        if revised_assistant.uncertainty == "LLM error":
            raise ChatResendGenerationError("The LLM could not produce a revised response")
        if replacement_original is None:
            raise ChatResendConflictError("The original message pair could not be locked")
        _delete_chat_message_records(replacement_original, session)
        session.commit()
        session.refresh(revised_assistant)
        return revised_assistant
    except Exception:
        session.rollback()
        raise


def _validate_resend_target(
    session_id: str,
    message_id: str,
    expected_assistant_message_id: str,
    session: Session,
    *,
    populate_existing: bool = False,
) -> tuple[ChatMessage, ChatMessage]:
    original = session.get(ChatMessage, message_id, populate_existing=populate_existing)
    if original is None or original.session_id != session_id:
        raise LookupError("Message not found in this session")
    if original.role != "user":
        raise ValueError("Only user messages can be edited and resent")

    original_assistant = _following_assistant(original, session)
    if original_assistant is None or original_assistant.id != expected_assistant_message_id:
        raise ChatResendConflictError(
            "The original message pair has changed; refresh and try again"
        )
    latest = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(
            ChatMessage.sequence_index.is_(None),
            ChatMessage.sequence_index.desc(),
            _ROLE_ORDER.desc(),
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .limit(1)
    ).first()
    if latest is None or latest.id != original_assistant.id:
        raise ChatResendConflictError("Only the latest complete exchange can be edited and resent")

    return original, original_assistant
