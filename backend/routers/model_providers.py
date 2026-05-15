from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models.model_provider import (
    ModelProvider,
    ModelProviderCreate,
    ModelProviderRead,
    ModelProviderUpdate,
)
from models.topic import Topic

router = APIRouter(prefix="/providers", tags=["providers"])

VALID_PROVIDER_TYPE = "openai_compatible"


def _validate_create(body: ModelProviderCreate) -> None:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty")
    if body.provider_type != VALID_PROVIDER_TYPE:
        raise HTTPException(
            status_code=422,
            detail=f"provider_type must be '{VALID_PROVIDER_TYPE}'",
        )
    if not body.base_url.strip():
        raise HTTPException(status_code=422, detail="base_url must not be empty")
    if not body.api_key.strip():
        raise HTTPException(status_code=422, detail="api_key must not be empty")
    # model_name is optional — can be set later or overridden per-topic


def _set_default(session: Session, provider: ModelProvider) -> None:
    if provider.is_default:
        others = session.exec(
            select(ModelProvider).where(
                ModelProvider.id != provider.id,
                ModelProvider.is_default == True,  # noqa: E712
            )
        ).all()
        for other in others:
            other.is_default = False
            session.add(other)


def _to_read(provider: ModelProvider) -> ModelProviderRead:
    return ModelProviderRead(
        **provider.model_dump(exclude={"api_key"}),
        masked_api_key=provider.masked_api_key,
    )


@router.post("", status_code=201)
def create_provider(
    body: ModelProviderCreate, session: Session = Depends(get_session)
) -> ModelProviderRead:
    _validate_create(body)

    existing = session.exec(select(ModelProvider).where(ModelProvider.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Provider name already exists")

    provider = ModelProvider(**body.model_dump())
    session.add(provider)
    session.flush()
    _set_default(session, provider)
    session.commit()
    session.refresh(provider)
    return _to_read(provider)


@router.get("")
def list_providers(session: Session = Depends(get_session)) -> dict:
    providers = session.exec(select(ModelProvider).order_by(ModelProvider.created_at.desc())).all()
    return {"providers": [_to_read(p).model_dump() for p in providers]}


@router.get("/{provider_id}")
def get_provider(provider_id: str, session: Session = Depends(get_session)) -> ModelProviderRead:
    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_read(provider)


@router.patch("/{provider_id}")
def update_provider(
    provider_id: str,
    body: ModelProviderUpdate,
    session: Session = Depends(get_session),
) -> ModelProviderRead:
    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = body.model_dump(exclude_unset=True)

    if "name" in update_data:
        if not update_data["name"].strip():
            raise HTTPException(status_code=422, detail="name must not be empty")
        existing = session.exec(
            select(ModelProvider).where(
                ModelProvider.name == update_data["name"],
                ModelProvider.id != provider_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Provider name already exists")

    if "provider_type" in update_data:
        if update_data["provider_type"] != VALID_PROVIDER_TYPE:
            raise HTTPException(
                status_code=422,
                detail=f"provider_type must be '{VALID_PROVIDER_TYPE}'",
            )

    for key, value in update_data.items():
        setattr(provider, key, value)
    provider.updated_at = datetime.now(timezone.utc)  # type: ignore[union-attr]

    session.add(provider)
    session.flush()
    _set_default(session, provider)
    session.commit()
    session.refresh(provider)
    return _to_read(provider)


@router.post("/{provider_id}/test")
def test_provider(provider_id: str, session: Session = Depends(get_session)) -> dict:
    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    from services.provider_test_service import test_provider as _test

    return _test(provider_id, session)


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, session: Session = Depends(get_session)) -> dict:
    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    in_use = session.exec(select(Topic).where(Topic.provider_id == provider_id)).first()
    if in_use:
        raise HTTPException(status_code=409, detail="Provider is in use by one or more Topics")

    session.delete(provider)
    session.commit()
    return {"deleted": True}
