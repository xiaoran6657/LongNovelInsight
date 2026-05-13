from pathlib import Path

PROMPT_FILES = {
    "overview": "overview.md",
    "characters": "characters.md",
    "relations": "relations.md",
    "events": "events.md",
    "causality": "causality.md",
    "themes": "themes.md",
}


def load_prompt(output_type: str) -> str:
    filename = PROMPT_FILES.get(output_type)
    if filename is None:
        raise ValueError(f"Unknown output_type: {output_type}")

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    filepath = prompts_dir / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")

    return filepath.read_text(encoding="utf-8")
