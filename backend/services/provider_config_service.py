"""Effective provider config resolution and topic-level provider config management."""

from sqlmodel import Session, select

from models.chunk import Chunk
from models.document import Document
from models.model_provider import ModelProvider
from models.topic import Topic
from models.topic_provider_config import (
    EffectiveProviderConfig,
    TopicProviderConfig,
    TopicProviderConfigCreate,
    TopicProviderConfigRead,
)
from provider_presets import detect_preset, get_model_preset


def _resolve_effective(
    session: Session,
    topic_id: str,
) -> EffectiveProviderConfig:
    """Resolve effective provider config: topic override > provider default > preset default."""
    result = EffectiveProviderConfig()

    # Load topic and topic-level config
    topic = session.get(Topic, topic_id)
    if topic is None:
        result.missing_fields.append("topic")
        return result

    tpc = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()

    provider_id = tpc.provider_id if (tpc and tpc.provider_id) else topic.provider_id
    provider = None
    if provider_id:
        provider = session.get(ModelProvider, provider_id)

    if provider is None:
        result.missing_fields.append("provider")
        result.warnings.append("No provider selected")
        return result

    result.provider_id = provider.id
    result.provider_name = provider.name

    # Detect provider preset from base_url
    bu = tpc.base_url_override if tpc and tpc.base_url_override else provider.base_url
    preset = detect_preset(bu)
    result.provider_key = preset.provider_key if preset else "openai_compatible"
    result.base_url = bu

    # Model name: topic override > provider > preset default
    model_name = None
    if tpc and tpc.model_name_override:
        model_name = tpc.model_name_override
    elif provider.model_name:
        model_name = provider.model_name
    elif preset and preset.default_model_name:
        model_name = preset.default_model_name

    if model_name:
        result.model_name = model_name
    else:
        result.missing_fields.append("model_name")

    # Context window
    cw = None
    if tpc and tpc.context_window_override is not None:
        cw = tpc.context_window_override
    elif provider.context_window > 0:
        cw = provider.context_window
    if cw and cw > 0:
        result.context_window = cw

    # Max output tokens
    mot = None
    if tpc and tpc.max_output_tokens_override is not None:
        mot = tpc.max_output_tokens_override
    elif provider.max_output_tokens > 0:
        mot = provider.max_output_tokens

    # If still unset, use model preset or per-type defaults
    model_preset = None
    if model_name and preset:
        model_preset = get_model_preset(preset.provider_key, model_name)
    if mot is None or mot <= 0:
        if model_preset and model_preset.recommended_max_output_tokens:
            mot = model_preset.recommended_max_output_tokens
        else:
            mot = 2048
    result.max_output_tokens = mot

    # Temperature
    temp = None
    if tpc and tpc.temperature_override is not None:
        temp = tpc.temperature_override
    elif provider.temperature > 0:
        temp = provider.temperature
    elif model_preset and model_preset.default_temperature is not None:
        temp = model_preset.default_temperature
    else:
        temp = 0.1
    result.temperature = temp

    # Thinking mode
    think = "disabled"
    if tpc and tpc.thinking_mode_override:
        think = tpc.thinking_mode_override
    elif model_preset and model_preset.default_thinking_mode != "provider_default":
        think = model_preset.default_thinking_mode
    result.thinking_mode = think

    # Reasoning effort
    if tpc and tpc.reasoning_effort_override:
        result.reasoning_effort = tpc.reasoning_effort_override

    # Parallelism
    parallel = 3
    if tpc and tpc.analysis_parallelism_override is not None:
        parallel = tpc.analysis_parallelism_override
    result.analysis_parallelism = max(1, min(parallel, 6))

    # Model capability flags
    if model_preset:
        result.supports_json_output = model_preset.supports_json_output
        result.supports_thinking = model_preset.supports_thinking

    # Readiness
    result.is_ready = bool(result.provider_id and result.base_url and result.model_name)

    return result


# ── CRUD ──


def get_topic_provider_config(session: Session, topic_id: str) -> TopicProviderConfigRead | None:
    tpc = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()
    if tpc is None:
        return None
    return TopicProviderConfigRead.model_validate(tpc)


def upsert_topic_provider_config(
    session: Session,
    topic_id: str,
    data: TopicProviderConfigCreate,
) -> TopicProviderConfigRead:
    from datetime import datetime, timezone

    tpc = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()

    if tpc is None:
        tpc = TopicProviderConfig(
            topic_id=topic_id,
            **data.model_dump(exclude_none=True),
        )
    else:
        update = data.model_dump(exclude_none=True)
        for k, v in update.items():
            setattr(tpc, k, v)
        tpc.updated_at = datetime.now(timezone.utc)  # type: ignore[union-attr]

    session.add(tpc)
    session.commit()
    session.refresh(tpc)
    return TopicProviderConfigRead.model_validate(tpc)


def get_effective_config(
    session: Session,
    topic_id: str,
) -> EffectiveProviderConfig:
    return _resolve_effective(session, topic_id)


def get_recommendation(session: Session, topic_id: str) -> dict:
    """Generate analysis recommendation based on document size."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        return {"error": "Topic not found"}

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()

    total_chars = sum(c.char_count for c in chunks) if chunks else (doc.char_count if doc else 0)
    chunk_count = len(chunks)
    est_tokens = int(total_chars / 2.0)  # rough for Chinese text

    # Size categories
    if total_chars <= 50_000:
        size = "small"
    elif total_chars <= 300_000:
        size = "medium"
    elif total_chars <= 1_000_000:
        size = "large"
    else:
        size = "huge"

    if total_chars == 0:
        size = "unknown"
        mode = "preview"
        limit = None
    elif size == "small":
        mode = "direct"
        limit = min(chunk_count, 10)
    elif size == "medium":
        mode = "direct"
        limit = min(chunk_count, 6)
    elif size == "large":
        mode = "preview"
        limit = min(chunk_count, 3)
    else:
        mode = "map_reduce_required"
        limit = None

    return {
        "size_category": size,
        "total_chars": total_chars,
        "estimated_input_tokens": est_tokens,
        "chunk_count": chunk_count,
        "recommended_model_name": "deepseek-v4-flash",
        "recommended_context_window": 1_000_000,
        "recommended_max_output_tokens": 2048,
        "recommended_temperature": 0.1,
        "recommended_thinking_mode": "disabled",
        "recommended_parallelism": 6 if size in ("small", "medium") else 3,
        "recommended_limit_chunks": limit,
        "recommended_analysis_mode": mode,
        "warnings": _recommendation_warnings(size, mode),
        "rationale": _recommendation_rationale(size, mode, total_chars),
    }


def _recommendation_warnings(size: str, mode: str) -> list[str]:
    w = []
    if size in ("large", "huge"):
        w.append(
            "Direct analysis repeats selected chunks ~6 times. "
            "Consider preview mode with small limit_chunks first."
        )
    if mode == "map_reduce_required":
        w.append(
            "Document is too large for v0.1 direct analysis. "
            "Use preview mode or wait for v0.2 map-reduce pipeline."
        )
    return w


def _recommendation_rationale(size: str, mode: str, chars: int) -> list[str]:
    r = []
    if size == "small":
        r.append(f"{chars:,} characters fits within a single direct analysis batch.")
        r.append("Using fast non-thinking model with max parallelism.")
    elif size == "medium":
        r.append(f"{chars:,} characters — moderate size. Limit chunks to avoid excessive API cost.")
        r.append("Non-thinking mode recommended for structured extraction speed.")
    elif size == "large":
        r.append(f"{chars:,} characters — large text. Preview mode strongly recommended.")
    elif size == "huge":
        r.append("Over 1M characters — do NOT run full direct analysis in v0.1.")
        r.append("Wait for v0.2 map-reduce pipeline.")
    return r
