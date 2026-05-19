"""Parse and validate v0.2 local_extraction LLM responses.

Pure Python — no LLM calls, no DB access.
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class ParseResult:
    ok: bool
    parsed: dict | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def parse_json_object(raw_text: str) -> ParseResult:
    """Parse a JSON object from LLM response text.

    Handles:
    - Pure JSON: {"key": "value"}
    - Markdown code fence: ```json ... ```
    - Generic code fence: ``` ... ```
    - Leading/trailing text around the JSON object
    """
    text = raw_text.strip()
    if not text:
        return ParseResult(ok=False, error="Empty response")

    # Try direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return ParseResult(ok=True, parsed=parsed)
        return ParseResult(
            ok=False,
            error=f"JSON is not a dict, got {type(parsed).__name__}",
        )
    except json.JSONDecodeError:
        pass

    # Try stripping markdown code fences
    # Match ```json ... ``` or ``` ... ```
    fence_patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"```json\s*(.*?)\s*```",
    ]
    for pat in fence_patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            inner = m.group(1).strip()
            try:
                parsed = json.loads(inner)
                if isinstance(parsed, dict):
                    return ParseResult(ok=True, parsed=parsed, warnings=["stripped code fence"])
                return ParseResult(
                    ok=False,
                    error=f"Code-fence content is not a dict, got {type(parsed).__name__}",
                )
            except json.JSONDecodeError:
                pass

    # Try to find a JSON object with braces
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return ParseResult(
                    ok=True, parsed=parsed, warnings=["extracted from surrounding text"]
                )
        except json.JSONDecodeError:
            pass

    return ParseResult(ok=False, error="Failed to parse JSON from response")


@dataclass
class ValidationResult:
    ok: bool
    data: dict
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.ok and len(self.errors) == 0


def validate_local_extraction_response(
    data: dict,
    expected_chunk_id: str,
) -> ValidationResult:
    """Validate a parsed local_extraction response against the contract.

    Checks:
    - Required top-level fields present (analysis_type, chunk_id)
    - chunk_id matches expected
    - Atom lists are lists (not dicts or null)
    - Key fields per atom are present (source_chunk_ids, evidence_quotes)
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Top-level required fields
    analysis_type = data.get("analysis_type")
    if not analysis_type or not isinstance(analysis_type, str):
        errors.append("Missing or invalid 'analysis_type'")
    elif analysis_type != "local_extraction":
        details = repr(analysis_type) if len(str(analysis_type)) <= 30 else "unexpected value"
        errors.append(f"analysis_type must be 'local_extraction', got {details}")

    chunk_id = data.get("chunk_id")
    if not chunk_id or not isinstance(chunk_id, str):
        errors.append("Missing or invalid 'chunk_id'")
    elif chunk_id != expected_chunk_id:
        errors.append(f"chunk_id mismatch: expected '{expected_chunk_id}', got '{chunk_id}'")

    # Check atom keys
    atom_keys = [
        "local_characters",
        "local_events",
        "local_relations",
        "local_causal_links",
        "local_theme_signals",
        "local_worldbuilding",
        "local_foreshadowing",
        "local_open_questions",
    ]

    for key in atom_keys:
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            if isinstance(val, dict):
                warnings.append(f"{key}: is a dict, not a list (will be auto-coerced)")
            else:
                warnings.append(f"{key}: is not a list (got {type(val).__name__})")
            continue
        for i, item in enumerate(val):
            if not isinstance(item, dict):
                errors.append(f"{key}[{i}]: not a dict")
                continue
            if "source_chunk_ids" not in item:
                warnings.append(f"{key}[{i}]: missing source_chunk_ids")
            if "evidence_quotes" not in item:
                warnings.append(f"{key}[{i}]: missing evidence_quotes")

    ok = len(errors) == 0
    return ValidationResult(ok=ok, data=data, warnings=warnings, errors=errors)
