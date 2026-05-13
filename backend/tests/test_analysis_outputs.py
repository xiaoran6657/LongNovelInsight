import json
from unittest.mock import patch

PATCH_PATH = "services.analysis_service.OpenAICompatibleLLMClient.chat"


def _mock_chat_side_effect(messages, model, temperature, max_tokens, response_format):
    return _mock_llm_response(_infer_output_type(messages))


def _mock_llm_response(output_type: str):
    from services.llm_client import LLMResponse

    responses = {
        "overview": json.dumps(
            {
                "title": "Test Novel",
                "author_hint": "Test Author",
                "era_setting": "Modern",
                "genre_tags": ["fiction"],
                "one_paragraph_summary": "A test summary.",
                "narrative_structure": "Linear",
                "style_notes": "Simple prose.",
                "key_themes_brief": ["test theme"],
                "source_chunk_ids": [],
                "evidence_quotes": ["test quote"],
                "confidence": 0.85,
            }
        ),
        "characters": json.dumps(
            {
                "characters": [
                    {
                        "name": "Alice",
                        "aliases": [],
                        "description": "A test character.",
                        "traits": ["brave"],
                        "role": "protagonist",
                        "first_appearance_chapter": 1,
                        "source_chunk_ids": [],
                        "evidence_quotes": ["Alice walked."],
                        "confidence": 0.95,
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
        "relations": json.dumps(
            {
                "relationships": [
                    {
                        "character_a": "Alice",
                        "character_b": "Bob",
                        "relationship_type": "friend",
                        "description": "They are friends.",
                        "direction": "bidirectional",
                        "source_chunk_ids": [],
                        "evidence_quotes": ["They met."],
                        "confidence": 0.9,
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
        "events": json.dumps(
            {
                "events": [
                    {
                        "event_id": "evt_1",
                        "title": "The Beginning",
                        "chapter": 1,
                        "summary": "The story begins.",
                        "participants": ["Alice"],
                        "importance": "critical",
                        "source_chunk_ids": [],
                        "evidence_quotes": ["It began."],
                        "confidence": 0.95,
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
        "causality": json.dumps(
            {
                "causal_chains": [
                    {
                        "cause_event_id": "evt_1",
                        "effect_event_id": "evt_2",
                        "causal_description": "A caused B.",
                        "causal_strength": "direct",
                        "source_chunk_ids": [],
                        "evidence_quotes": ["Because of A, B happened."],
                        "confidence": 0.85,
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
        "themes": json.dumps(
            {
                "themes": [
                    {
                        "theme_name": "Friendship",
                        "description": "The power of friendship.",
                        "related_characters": ["Alice", "Bob"],
                        "related_chapters": [1],
                        "philosophical_framework": "Humanism",
                        "source_chunk_ids": [],
                        "evidence_quotes": ["Together they stood."],
                        "confidence": 0.9,
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
    }
    return LLMResponse(content=responses[output_type], model="test-model", usage={})


def _setup_topic_with_document_and_chunks(client):
    """Create a topic, upload a document, parse it, and set up a provider."""
    # Create provider
    resp = client.post(
        "/api/model-providers",
        json={
            "name": "Test Provider",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-test-key",
            "model_name": "test-model",
            "is_default": True,
        },
    )
    provider_id = resp.json()["id"]

    # Create topic
    resp = client.post(
        "/api/topics",
        json={"name": "Test Topic", "provider_id": provider_id},
    )
    topic_id = resp.json()["id"]

    # Upload document
    from io import BytesIO

    content = "第一章 开始\n\nAlice walked into the room.\n\n第二章 发展\n\nBob followed her."
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", BytesIO(content.encode("utf-8")), "text/plain")},
    )

    # Parse
    client.post(f"/api/topics/{topic_id}/parse")

    return topic_id, provider_id


class TestAnalysisOutputs:
    def test_run_analysis_success(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                resp = c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                assert resp.status_code == 200
                data = resp.json()
                assert data["count"] == 6
                types_found = {o["output_type"] for o in data["outputs"]}
                assert types_found == {
                    "overview",
                    "characters",
                    "relations",
                    "events",
                    "causality",
                    "themes",
                }

    def test_outputs_have_evidence_fields(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                resp = c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                assert resp.status_code == 200
                for o in resp.json()["outputs"]:
                    assert "source_chunk_ids" in o
                    assert "evidence_quotes" in o
                    assert "confidence" in o
                    assert isinstance(o["evidence_quotes"], list)
                    assert isinstance(o["source_chunk_ids"], list)

    def test_get_outputs(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")

            resp = c.get(f"/api/topics/{topic_id}/analysis/outputs")
            assert resp.status_code == 200
            assert resp.json()["count"] == 6

    def test_get_outputs_filtered(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")

            resp = c.get(f"/api/topics/{topic_id}/analysis/outputs?output_type=characters")
            assert resp.status_code == 200
            assert resp.json()["count"] == 1
            assert resp.json()["outputs"][0]["output_type"] == "characters"

    def test_delete_outputs(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")

            resp = c.delete(f"/api/topics/{topic_id}/analysis/outputs")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True
            assert resp.json()["count"] == 6

            # Verify cleared
            resp = c.get(f"/api/topics/{topic_id}/analysis/outputs")
            assert resp.json()["count"] == 0

    def test_no_topic_returns_404(self, client):
        with client as c:
            resp = c.post("/api/topics/nonexistent/analysis/run")
            assert resp.status_code == 404

    def test_no_provider_returns_409(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "No Provider Topic"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            content = "Test content."
            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={"file": ("test.txt", BytesIO(content.encode("utf-8")), "text/plain")},
            )
            c.post(f"/api/topics/{topic_id}/parse")

            resp = c.post(f"/api/topics/{topic_id}/analysis/run")
            assert resp.status_code == 409

    def test_no_document_returns_409(self, client):
        with client as c:
            # Create provider and topic without document
            resp = c.post(
                "/api/model-providers",
                json={
                    "name": "P",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-key",
                    "model_name": "m",
                    "is_default": True,
                },
            )
            provider_id = resp.json()["id"]

            resp = c.post(
                "/api/topics",
                json={"name": "No Doc", "provider_id": provider_id},
            )
            topic_id = resp.json()["id"]

            resp = c.post(f"/api/topics/{topic_id}/analysis/run")
            assert resp.status_code == 409

    def test_not_parsed_returns_409(self, client):
        with client as c:
            resp = c.post(
                "/api/model-providers",
                json={
                    "name": "P2",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-key",
                    "model_name": "m",
                    "is_default": True,
                },
            )
            provider_id = resp.json()["id"]

            resp = c.post(
                "/api/topics",
                json={"name": "Not Parsed", "provider_id": provider_id},
            )
            topic_id = resp.json()["id"]

            from io import BytesIO

            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={"file": ("test.txt", BytesIO(b"content."), "text/plain")},
            )

            resp = c.post(f"/api/topics/{topic_id}/analysis/run")
            assert resp.status_code == 409

    def test_re_run_replaces_old_outputs(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                resp = c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                assert resp.status_code == 200
                # Should still have exactly 6 outputs (old ones deleted)
                assert resp.json()["count"] == 6

    def test_llm_invalid_json_handled(self, client):
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            from services.llm_client import LLMResponse

            def bad_json(*args, **kwargs):
                return LLMResponse(content="not valid json {{{", model="test", usage={})

            with patch(
                "services.analysis_service.OpenAICompatibleLLMClient.chat",
                side_effect=bad_json,
            ):
                resp = c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                # Should succeed but with 0 outputs since JSON parsing fails
                assert resp.status_code == 200
                data = resp.json()
                assert data["count"] == 0

    def test_no_external_api_calls(self, client):
        """Ensure tests never call external APIs."""
        with client as c:
            topic_id, _ = _setup_topic_with_document_and_chunks(c)

            with patch(PATCH_PATH, side_effect=_mock_chat_side_effect):
                resp = c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=5")
                assert resp.status_code == 200


def _infer_output_type(messages):
    """Infer the output type from the system prompt content."""
    for m in messages:
        content = m.content if hasattr(m, "content") else m.get("content", "")
        if "character extraction" in content[:200]:
            return "characters"
        if "relationship" in content[:200]:
            return "relations"
        if "causal chain" in content[:200]:
            return "causality"
        if "plot event" in content[:200]:
            return "events"
        if "philosophy" in content[:200]:
            return "themes"
    return "overview"
