"""Tests for v0.2 prompt loading and response parser."""

import json

import pytest

from services.analysis_response_parser import (
    parse_json_object,
    validate_local_extraction_response,
)
from services.prompt_loader import (
    V2_PROMPT_FILES,
    load_local_extraction_prompt,
    load_merge_prompt,
    load_prompt,
    load_v2_prompt,
)


class TestV1PromptCompatibility:
    def test_v1_overview_loads(self):
        prompt = load_prompt("overview")
        assert len(prompt) > 100
        assert "json" in prompt.lower()

    def test_v1_all_types_load(self):
        for t in ("overview", "characters", "relations", "events", "causality", "themes"):
            prompt = load_prompt(t)
            assert len(prompt) > 50, f"Prompt too short for {t}"

    def test_v1_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown v1 output_type"):
            load_prompt("nonexistent_type")


class TestV2PromptLoading:
    def test_local_extraction_loads(self):
        prompt = load_v2_prompt("local_extraction")
        assert "local_extraction" in prompt.lower() or "local_characters" in prompt.lower()

    def test_local_extraction_shortcut(self):
        prompt = load_local_extraction_prompt()
        assert len(prompt) > 100

    def test_merge_prompts_load(self):
        for merge_type in ("characters", "events", "relations", "causality", "themes", "overview"):
            prompt = load_v2_prompt(f"merge_{merge_type}")
            assert len(prompt) > 50, f"merge_{merge_type} too short"

    def test_merge_prompt_shortcut(self):
        prompt = load_merge_prompt("characters")
        assert len(prompt) > 50

    def test_unknown_v2_prompt_raises(self):
        with pytest.raises(ValueError, match="Unknown v2 prompt_name"):
            load_v2_prompt("nonexistent")

    def test_v2_prompt_file_missing_raises(self):
        """If a prompt file doesn't exist on disk, raise FileNotFoundError."""
        # Temporarily break the mapping
        old = V2_PROMPT_FILES.get("local_extraction")
        V2_PROMPT_FILES["local_extraction"] = "nonexistent/file.md"
        try:
            with pytest.raises(FileNotFoundError):
                load_v2_prompt("local_extraction")
        finally:
            if old:
                V2_PROMPT_FILES["local_extraction"] = old
            else:
                del V2_PROMPT_FILES["local_extraction"]

    def test_all_v2_prompts_exist_on_disk(self):
        """Every entry in V2_PROMPT_FILES points to an existing file."""
        for name in V2_PROMPT_FILES:
            prompt = load_v2_prompt(name)
            assert len(prompt) > 0, f"V2 prompt '{name}' is empty"


class TestParseJsonObject:
    def test_pure_json_dict(self):
        r = parse_json_object('{"key": "value"}')
        assert r.ok
        assert r.parsed == {"key": "value"}

    def test_json_with_whitespace(self):
        r = parse_json_object('  \n{"key": "value"}\n  ')
        assert r.ok
        assert r.parsed == {"key": "value"}

    def test_markdown_code_fence_with_lang(self):
        r = parse_json_object('```json\n{"a": 1}\n```')
        assert r.ok
        assert r.parsed == {"a": 1}

    def test_markdown_code_fence_no_lang(self):
        r = parse_json_object('```\n{"a": 1}\n```')
        assert r.ok
        assert r.parsed == {"a": 1}

    def test_json_embedded_in_text(self):
        r = parse_json_object('Here is the result: {"a": 1} Done.')
        assert r.ok
        assert r.parsed == {"a": 1}

    def test_invalid_json(self):
        r = parse_json_object("not json at all {{{")
        assert not r.ok
        assert r.error is not None

    def test_empty_string(self):
        r = parse_json_object("")
        assert not r.ok

    def test_json_array_returns_error(self):
        r = parse_json_object("[1, 2, 3]")
        assert not r.ok
        assert "dict" in r.error.lower()

    def test_complex_local_extraction(self):
        data = json.dumps(
            {
                "analysis_type": "local_extraction",
                "chunk_id": "chunk-abc",
                "local_characters": [{"name": "张三", "source_chunk_ids": ["chunk-abc"]}],
            }
        )
        r = parse_json_object(data)
        assert r.ok
        assert r.parsed["analysis_type"] == "local_extraction"

    def test_code_fence_inline_no_newlines(self):
        r = parse_json_object('```json{"a": 1}```')
        assert r.ok
        assert r.parsed == {"a": 1}


class TestValidateLocalExtraction:
    def test_valid_response(self):
        data = {
            "analysis_type": "local_extraction",
            "chunk_id": "chunk-abc",
            "local_characters": [
                {
                    "character_id_hint": "x",
                    "source_chunk_ids": ["chunk-abc"],
                    "evidence_quotes": ["test"],
                }
            ],
        }
        result = validate_local_extraction_response(data, "chunk-abc")
        assert result.is_valid
        assert len(result.errors) == 0

    def test_chunk_id_mismatch(self):
        data = {"analysis_type": "local_extraction", "chunk_id": "wrong-id"}
        result = validate_local_extraction_response(data, "chunk-abc")
        assert not result.is_valid
        assert any("mismatch" in e.lower() for e in result.errors)

    def test_missing_analysis_type(self):
        data = {"chunk_id": "chunk-abc"}
        result = validate_local_extraction_response(data, "chunk-abc")
        assert any("analysis_type" in e.lower() for e in result.errors)

    def test_missing_chunk_id(self):
        data = {"analysis_type": "local_extraction"}
        result = validate_local_extraction_response(data, "chunk-abc")
        assert any("chunk_id" in e.lower() for e in result.errors)

    def test_dict_not_list_warns(self):
        data = {
            "analysis_type": "local_extraction",
            "chunk_id": "chunk-abc",
            "local_characters": {"item": {"name": "X"}},
        }
        result = validate_local_extraction_response(data, "chunk-abc")
        # dicts are auto-coerced in atom_normalizer, so just a warning
        assert any("dict" in w.lower() for w in result.warnings)

    def test_non_dict_item_errors(self):
        data = {
            "analysis_type": "local_extraction",
            "chunk_id": "chunk-abc",
            "local_characters": ["not a dict"],
        }
        result = validate_local_extraction_response(data, "chunk-abc")
        assert any("not a dict" in e.lower() for e in result.errors)

    def test_missing_source_chunk_ids_warns(self):
        data = {
            "analysis_type": "local_extraction",
            "chunk_id": "chunk-abc",
            "local_characters": [{"character_id_hint": "x"}],
        }
        result = validate_local_extraction_response(data, "chunk-abc")
        assert any("source_chunk_ids" in w.lower() for w in result.warnings)

    def test_empty_atom_keys_ok(self):
        data = {"analysis_type": "local_extraction", "chunk_id": "chunk-abc"}
        result = validate_local_extraction_response(data, "chunk-abc")
        assert result.is_valid

    def test_wrong_analysis_type_invalid(self):
        data = {"analysis_type": "overview", "chunk_id": "chunk-abc"}
        result = validate_local_extraction_response(data, "chunk-abc")
        assert not result.is_valid
        assert any("must be 'local_extraction'" in e.lower() for e in result.errors)

    def test_fenced_json_validates(self):
        raw = (
            "```json\n"
            + json.dumps(
                {
                    "analysis_type": "local_extraction",
                    "chunk_id": "chunk-abc",
                    "local_characters": [
                        {"name": "X", "evidence_quotes": ["e"], "source_chunk_ids": ["chunk-abc"]}
                    ],
                }
            )
            + "\n```"
        )
        parsed = parse_json_object(raw)
        assert parsed.ok
        result = validate_local_extraction_response(parsed.parsed, "chunk-abc")
        assert result.is_valid
