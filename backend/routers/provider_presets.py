from fastapi import APIRouter, Query

from provider_presets import detect_preset, get_preset, get_presets

router = APIRouter(prefix="/provider-presets", tags=["provider_presets"])


@router.get("")
def list_presets() -> dict:
    presets = [p.model_dump() for p in get_presets()]
    return {"presets": presets}


@router.get("/detect")
def detect(base_url: str = Query(...)) -> dict:
    preset = detect_preset(base_url)
    if preset is None:
        return {
            "provider_key": "openai_compatible",
            "display_name": "OpenAI-compatible custom",
            "base_urls": [],
            "models": [],
            "default_model_name": None,
        }
    return preset.model_dump()


@router.get("/{provider_key}")
def get_single_preset(provider_key: str) -> dict:
    preset = get_preset(provider_key)
    if preset is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Unknown provider key: {provider_key}")
    return preset.model_dump()
