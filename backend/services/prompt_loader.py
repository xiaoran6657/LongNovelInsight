from pathlib import Path

# v0.1 analysis types
PROMPT_FILES = {
    "overview": "overview.md",
    "characters": "characters.md",
    "relations": "relations.md",
    "events": "events.md",
    "causality": "causality.md",
    "themes": "themes.md",
}

# v0.2 staged pipeline prompts
V2_PROMPT_FILES = {
    "local_extraction": "local/local_extraction.md",
    "merge_characters": "merge/merge_characters.md",
    "merge_events": "merge/merge_events.md",
    "merge_relations": "merge/merge_relations.md",
    "merge_causality": "merge/merge_causality.md",
    "merge_themes": "merge/merge_themes.md",
    "merge_overview": "merge/merge_overview.md",
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
    """Load a v0.1 analysis prompt by type name."""
    global _SHARED_RULES
    if _SHARED_RULES is None:
        _SHARED_RULES = _load_shared_rules()

    filename = PROMPT_FILES.get(output_type)
    if filename is None:
        raise ValueError(f"Unknown v1 output_type: {output_type}")

    filepath = _PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    prompt = filepath.read_text(encoding="utf-8")
    if _SHARED_RULES:
        prompt = _SHARED_RULES + prompt
    return prompt


def load_v2_prompt(prompt_name: str) -> str:
    """Load a v0.2 staged pipeline prompt by name.

    Supported names: local_extraction, merge_<type>.
    Shared rules are NOT prepended automatically; v2 prompts may use
    different shared contract fragments.
    """
    filename = V2_PROMPT_FILES.get(prompt_name)
    if filename is None:
        raise ValueError(
            f"Unknown v2 prompt_name: {prompt_name}. Supported: {list(V2_PROMPT_FILES)}"
        )

    filepath = _PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"v2 prompt file not found: {filepath}")

    return filepath.read_text(encoding="utf-8")


def load_local_extraction_prompt() -> str:
    """Load the v0.2 local_extraction prompt."""
    return load_v2_prompt("local_extraction")


def load_merge_prompt(merge_type: str) -> str:
    """Load a v0.2 merge prompt by type (e.g. 'characters', 'events')."""
    return load_v2_prompt(f"merge_{merge_type}")
