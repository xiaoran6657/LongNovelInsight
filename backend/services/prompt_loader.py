from pathlib import Path

PROMPT_FILES = {
    "overview": "overview.md",
    "characters": "characters.md",
    "relations": "relations.md",
    "events": "events.md",
    "causality": "causality.md",
    "themes": "themes.md",
}

_SHARED_RULES: str | None = None
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_shared_rules() -> str:
    """Load all shared prompt fragments and return them as a combined header."""
    shared_dir = _PROMPTS_DIR / "shared"
    if not shared_dir.exists():
        return ""
    parts: list[str] = []
    for f in sorted(shared_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8").strip()
        if content:
            parts.append(content)
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\n---\n\n"


def load_prompt(output_type: str) -> str:
    global _SHARED_RULES
    if _SHARED_RULES is None:
        _SHARED_RULES = _load_shared_rules()

    filename = PROMPT_FILES.get(output_type)
    if filename is None:
        raise ValueError(f"Unknown output_type: {output_type}")

    filepath = _PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    prompt = filepath.read_text(encoding="utf-8")
    if _SHARED_RULES:
        prompt = _SHARED_RULES + prompt
    return prompt
