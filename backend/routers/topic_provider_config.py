"""Topic-level provider configuration and recommendation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.topic import Topic
from models.topic_provider_config import (
    EffectiveProviderConfig,
    TopicProviderConfigCreate,
    TopicProviderConfigRead,
)
from services import provider_config_service

router = APIRouter(prefix="/topics/{topic_id}", tags=["topic_provider_config"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.get("/provider-config")
def get_config(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    cfg = provider_config_service.get_topic_provider_config(session, topic_id)
    if cfg is None:
        return {"config": None}
    return {"config": cfg.model_dump()}


@router.put("/provider-config")
def upsert_config(
    topic_id: str,
    body: TopicProviderConfigCreate,
    session: Session = Depends(get_session),
) -> TopicProviderConfigRead:
    _check_topic(topic_id, session)

    # Validate numeric ranges
    if body.context_window_override is not None and body.context_window_override <= 0:
        raise HTTPException(status_code=422, detail="context_window_override must be > 0")
    if body.max_output_tokens_override is not None and body.max_output_tokens_override <= 0:
        raise HTTPException(status_code=422, detail="max_output_tokens_override must be > 0")
    if body.temperature_override is not None and not (0.0 <= body.temperature_override <= 2.0):
        raise HTTPException(status_code=422, detail="temperature must be 0-2")
    if body.analysis_parallelism_override is not None and not (
        1 <= body.analysis_parallelism_override <= 6
    ):
        raise HTTPException(status_code=422, detail="analysis_parallelism must be 1-6")

    return provider_config_service.upsert_topic_provider_config(session, topic_id, body)


@router.get("/provider-config/effective")
def get_effective(
    topic_id: str, session: Session = Depends(get_session)
) -> EffectiveProviderConfig:
    _check_topic(topic_id, session)
    return provider_config_service.get_effective_config(session, topic_id)


@router.get("/analysis/recommendation")
def get_recommendation(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    return provider_config_service.get_recommendation(session, topic_id)


@router.post("/provider-config/apply-recommendation")
def apply_recommendation(topic_id: str, session: Session = Depends(get_session)) -> dict:
    _check_topic(topic_id, session)
    rec = provider_config_service.get_recommendation(session, topic_id)

    body = TopicProviderConfigCreate(
        model_name_override=rec.get("recommended_model_name"),
        max_output_tokens_override=rec.get("recommended_max_output_tokens"),
        temperature_override=rec.get("recommended_temperature"),
        thinking_mode_override=rec.get("recommended_thinking_mode"),
        analysis_parallelism_override=rec.get("recommended_parallelism"),
        recommended_profile=rec.get("size_category"),
    )

    cfg = provider_config_service.upsert_topic_provider_config(session, topic_id, body)
    return {"config": cfg.model_dump(), "recommendation": rec}
