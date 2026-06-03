"""v0.4 Cross-work entity registry and build API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from db import get_session
from models.entity_mention import EntityMention
from models.global_entity import GlobalEntity
from models.topic import Topic

router = APIRouter(prefix="/topics/{topic_id}", tags=["cross_work"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.get("/entities")
def list_entities(
    topic_id: str,
    entity_type: str | None = Query(None),
    work_id: str | None = Query(None),
    q: str | None = Query(None),
    min_confidence: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("mention_count"),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    base = select(GlobalEntity).where(GlobalEntity.topic_id == topic_id)

    if entity_type:
        base = base.where(GlobalEntity.entity_type == entity_type)
    if q:
        base = base.where(GlobalEntity.canonical_name.contains(q))
    if min_confidence is not None:
        base = base.where(GlobalEntity.confidence >= min_confidence)

    # Apply work_id filter via work_ids_json
    if work_id:
        base = base.where(
            GlobalEntity.work_ids_json.contains(f'"{work_id}"')  # type: ignore[arg-type]
        )

    sort_map = {
        "mention_count": GlobalEntity.mention_count.desc(),
        "name": GlobalEntity.canonical_name.asc(),
        "confidence": GlobalEntity.confidence.desc(),
        "work_count": GlobalEntity.mention_count.desc(),
    }
    order = sort_map.get(sort, GlobalEntity.mention_count.desc())

    total = len(session.exec(base).all())
    entities = session.exec(
        base.order_by(order).offset(offset).limit(limit)  # type: ignore[arg-type]
    ).all()

    return {
        "entities": [
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "canonical_name": e.canonical_name,
                "aliases": _safe_json_list(e.aliases_json),
                "work_ids": _safe_json_list(e.work_ids_json),
                "mention_count": e.mention_count,
                "evidence_count": e.evidence_count,
                "confidence": e.confidence,
                "merge_strategy": e.merge_strategy,
            }
            for e in entities
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/entities/{entity_id}")
def get_entity(
    topic_id: str,
    entity_id: str,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    entity = session.get(GlobalEntity, entity_id)
    if entity is None or entity.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "canonical_name": entity.canonical_name,
        "aliases": _safe_json_list(entity.aliases_json),
        "work_ids": _safe_json_list(entity.work_ids_json),
        "mention_count": entity.mention_count,
        "evidence_count": entity.evidence_count,
        "confidence": entity.confidence,
        "merge_strategy": entity.merge_strategy,
        "metadata": _safe_json_dict(entity.metadata_json),
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


@router.get("/entities/{entity_id}/mentions")
def list_entity_mentions(
    topic_id: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    entity = session.get(GlobalEntity, entity_id)
    if entity is None or entity.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Entity not found")

    base = select(EntityMention).where(
        EntityMention.topic_id == topic_id,
        EntityMention.global_entity_id == entity_id,
    )
    total = len(session.exec(base).all())
    mentions = session.exec(
        base.order_by(EntityMention.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return {
        "mentions": [
            {
                "id": m.id,
                "work_id": m.work_id,
                "source_type": m.source_type,
                "source_id": m.source_id,
                "chunk_id": m.chunk_id,
                "surface_text": m.surface_text,
                "evidence_text": m.evidence_text,
                "confidence": m.confidence,
                "metadata": _safe_json_dict(m.metadata_json),
            }
            for m in mentions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/cross-work/build", status_code=200)
def build_cross_work(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Build or rebuild the cross-work entity registry for this topic."""
    _check_topic(topic_id, session)

    from services.cross_work_entity_service import build_entity_registry

    result = build_entity_registry(topic_id, session)
    return result


def _safe_json_list(raw: str) -> list:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _safe_json_dict(raw: str | None) -> dict:
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ── Graph endpoints ──


@router.get("/graphs/characters")
def get_character_graph(
    topic_id: str,
    work_id: str | None = Query(None),
    min_confidence: float | None = Query(None),
    min_weight: int | None = Query(None),
    relation_type: str | None = Query(None),
    limit_nodes: int | None = Query(None),
    include_evidence: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    from services.cross_work_graph_service import get_latest_character_graph

    return get_latest_character_graph(
        topic_id,
        session,
        work_id=work_id,
        min_confidence=min_confidence,
        min_weight=min_weight,
        relation_type=relation_type,
        limit_nodes=limit_nodes,
        include_evidence=include_evidence,
    )


@router.post("/graphs/build", status_code=200)
def build_graph(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Build or rebuild the character relationship graph for this topic."""
    _check_topic(topic_id, session)

    from services.cross_work_graph_service import build_character_graph

    return build_character_graph(topic_id, session)


# ── Timeline endpoints ──


@router.get("/timeline")
def get_timeline(
    topic_id: str,
    work_id: str | None = Query(None),
    participant_entity_id: str | None = Query(None),
    min_confidence: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    from services.cross_work_timeline_service import get_timeline as svc_get

    return svc_get(
        topic_id,
        session,
        work_id=work_id,
        participant_entity_id=participant_entity_id,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )


@router.post("/timeline/build", status_code=200)
def build_timeline(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Build or rebuild the cross-work timeline for this topic."""
    _check_topic(topic_id, session)

    from services.cross_work_timeline_service import build_timeline as svc_build

    return svc_build(topic_id, session)
