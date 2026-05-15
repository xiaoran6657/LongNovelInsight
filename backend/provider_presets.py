"""Provider preset catalog — known provider base URLs, models, and defaults."""

from typing import Literal

from pydantic import BaseModel

# ── Data classes ──


class ProviderModelPreset(BaseModel):
    model_name: str
    display_name: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    recommended_max_output_tokens: int | None = None
    default_temperature: float | None = None
    supports_json_output: bool = True
    supports_thinking: bool = False
    default_thinking_mode: Literal["enabled", "disabled", "provider_default"] = "provider_default"
    notes: str | None = None
    tags: list[str] = []


class ProviderBaseUrlPreset(BaseModel):
    label: str
    base_url: str
    region: str | None = None
    provider_key: str


class ProviderPreset(BaseModel):
    provider_key: str
    display_name: str
    api_format: Literal["openai_chat_completions"] = "openai_chat_completions"
    base_urls: list[ProviderBaseUrlPreset] = []
    models: list[ProviderModelPreset] = []
    default_model_name: str | None = None


# ── Catalog ──

PRESETS: list[ProviderPreset] = [
    ProviderPreset(
        provider_key="deepseek",
        display_name="DeepSeek",
        base_urls=[
            ProviderBaseUrlPreset(
                label="DeepSeek OpenAI-compatible",
                base_url="https://api.deepseek.com",
                region="global",
                provider_key="deepseek",
            ),
        ],
        models=[
            ProviderModelPreset(
                model_name="deepseek-v4-flash",
                display_name="DeepSeek V4 Flash",
                context_window=1_000_000,
                recommended_max_output_tokens=2048,
                default_temperature=0.1,
                supports_json_output=True,
                supports_thinking=True,
                default_thinking_mode="disabled",
                tags=["fast", "recommended", "non-thinking-default"],
            ),
            ProviderModelPreset(
                model_name="deepseek-v4-pro",
                display_name="DeepSeek V4 Pro",
                context_window=1_000_000,
                recommended_max_output_tokens=3072,
                default_temperature=0.0,
                supports_json_output=True,
                supports_thinking=True,
                default_thinking_mode="disabled",
                tags=["quality", "slower"],
            ),
            ProviderModelPreset(
                model_name="deepseek-chat",
                display_name="DeepSeek Chat (legacy)",
                context_window=1_000_000,
                recommended_max_output_tokens=2048,
                default_temperature=0.2,
                supports_json_output=True,
                supports_thinking=False,
                default_thinking_mode="disabled",
                tags=["compatibility", "legacy"],
            ),
        ],
        default_model_name="deepseek-v4-flash",
    ),
    ProviderPreset(
        provider_key="openai",
        display_name="OpenAI",
        base_urls=[
            ProviderBaseUrlPreset(
                label="OpenAI API",
                base_url="https://api.openai.com/v1",
                region="global",
                provider_key="openai",
            ),
        ],
        models=[],
        default_model_name=None,
    ),
    ProviderPreset(
        provider_key="qwen",
        display_name="Qwen / Alibaba Model Studio",
        base_urls=[
            ProviderBaseUrlPreset(
                label="DashScope Singapore",
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                region="sg",
                provider_key="qwen",
            ),
            ProviderBaseUrlPreset(
                label="DashScope Beijing",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                region="cn-beijing",
                provider_key="qwen",
            ),
            ProviderBaseUrlPreset(
                label="DashScope US Virginia",
                base_url="https://dashscope-us.aliyuncs.com/compatible-mode/v1",
                region="us-va",
                provider_key="qwen",
            ),
            ProviderBaseUrlPreset(
                label="DashScope Hong Kong",
                base_url="https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1",
                region="cn-hk",
                provider_key="qwen",
            ),
        ],
        models=[],
        default_model_name=None,
    ),
    ProviderPreset(
        provider_key="moonshot",
        display_name="Kimi / Moonshot",
        base_urls=[
            ProviderBaseUrlPreset(
                label="Moonshot API",
                base_url="https://api.moonshot.ai/v1",
                region="global",
                provider_key="moonshot",
            ),
        ],
        models=[],
        default_model_name=None,
    ),
    ProviderPreset(
        provider_key="openai_compatible",
        display_name="OpenAI-compatible custom",
        api_format="openai_chat_completions",
        base_urls=[],
        models=[],
        default_model_name=None,
    ),
]

_BY_KEY: dict[str, ProviderPreset] = {p.provider_key: p for p in PRESETS}


# ── Helper functions ──


def get_presets() -> list[ProviderPreset]:
    return PRESETS


def get_preset(provider_key: str) -> ProviderPreset | None:
    return _BY_KEY.get(provider_key)


def detect_preset(base_url: str) -> ProviderPreset | None:
    """Detect provider preset by base_url. Normalizes trailing slash."""
    normalized = base_url.rstrip("/").lower()
    for preset in PRESETS:
        for bu in preset.base_urls:
            if bu.base_url.rstrip("/").lower() == normalized:
                return preset
    return None


def get_model_preset(provider_key: str, model_name: str) -> ProviderModelPreset | None:
    preset = get_preset(provider_key)
    if preset is None:
        return None
    for m in preset.models:
        if m.model_name == model_name:
            return m
    return None
