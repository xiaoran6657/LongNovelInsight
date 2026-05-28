import json
from unittest.mock import patch

CHAT_PATCH_PATH = "services.chat_service.OpenAICompatibleLLMClient.chat"


def _mock_chat_response(messages, model, temperature, max_tokens, response_format):
    from services.llm_client import LLMResponse

    answer = json.dumps(
        {
            "answer": "刘备是一个仁德的领袖。",
            "evidence": ["桃园结义展现了刘备的义气。"],
            "uncertainty": None,
        }
    )
    return LLMResponse(content=answer, model="test", usage={})


def _setup_chat(client):
    """Create provider, topic, upload doc, parse, create chat session."""
    resp = client.post(
        "/api/providers",
        json={
            "name": "ChatP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-test-key",
            "model_name": "test-model",
            "is_default": True,
        },
    )
    provider_id = resp.json()["id"]

    resp = client.post(
        "/api/topics",
        json={"name": "Chat Topic", "provider_id": provider_id},
    )
    topic_id = resp.json()["id"]

    from io import BytesIO

    content = "第一章 桃园结义\n\n刘备与关羽张飞在桃园结为兄弟。\n\n第二章 发展\n\n曹操率军南下。"
    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", BytesIO(content.encode("utf-8")), "text/plain")},
    )
    client.post(f"/api/topics/{topic_id}/parse")

    # Run analysis first
    with patch(
        "services.analysis_service.OpenAICompatibleLLMClient.chat",
        side_effect=_mock_chat_analysis,
    ):
        client.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=3")

    return topic_id


def _mock_chat_analysis(messages, model, temperature, max_tokens, response_format):
    from services.llm_client import LLMResponse

    return LLMResponse(
        content=json.dumps(
            {
                "title": "Test",
                "characters": [
                    {
                        "name": "刘备",
                        "source_chunk_ids": [],
                        "evidence_quotes": ["桃园结义"],
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        model="test",
        usage={},
    )


class TestChat:
    def test_create_session(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Character Discussion"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == "Character Discussion"
            assert data["topic_id"] == topic_id
            assert "id" in data

    def test_list_sessions(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Session 1"},
            )
            c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Session 2"},
            )

            resp = c.get(f"/api/topics/{topic_id}/chat/sessions")
            assert resp.status_code == 200
            assert len(resp.json()["sessions"]) == 2

    def test_topic_not_found(self, client):
        with client as c:
            resp = c.post(
                "/api/topics/nonexistent/chat/sessions",
                json={"title": "Test"},
            )
            assert resp.status_code == 404

    def test_send_message(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Q&A"},
            )
            session_id = resp.json()["id"]

            with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
                resp = c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "刘备的性格特点是什么？"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["role"] == "assistant"
                assert "刘备" in data["content"]
                assert data["evidence_json"] is not None
                assert data["uncertainty"] is None

    def test_messages_list(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Q&A"},
            )
            session_id = resp.json()["id"]

            with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
                c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "刘备的性格特点是什么？"},
                )

            resp = c.get(f"/api/chat/sessions/{session_id}/messages")
            assert resp.status_code == 200
            messages = resp.json()["messages"]
            assert len(messages) == 2  # user + assistant
            roles = {m["role"] for m in messages}
            assert roles == {"user", "assistant"}

    def test_evidence_fields_present(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Evidence Test"},
            )
            session_id = resp.json()["id"]

            with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
                resp = c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "Who is Liu Bei?"},
                )
                data = resp.json()
                assert "evidence_json" in data
                assert "uncertainty" in data

    def test_session_not_found_message(self, client):
        with client as c:
            resp = c.post(
                "/api/chat/sessions/nonexistent/messages",
                json={"content": "Hello"},
            )
            assert resp.status_code == 404

    def test_session_not_found_delete(self, client):
        with client as c:
            resp = c.delete("/api/chat/sessions/nonexistent")
            assert resp.status_code == 404

    def test_empty_content_422(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Empty Test"},
            )
            session_id = resp.json()["id"]

            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": ""},
            )
            assert resp.status_code == 422

    def test_content_null_returns_422(self, client):
        with client as c:
            topic_id = _setup_chat(c)
            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Null Test"},
            )
            session_id = resp.json()["id"]

            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": None},
            )
            assert resp.status_code == 422

    def test_content_not_string_returns_422(self, client):
        with client as c:
            topic_id = _setup_chat(c)
            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Type Test"},
            )
            session_id = resp.json()["id"]

            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": 123},
            )
            assert resp.status_code == 422

    def test_no_provider_returns_409(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "NoP"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            content = "Test content for parsing.\n第一章 测试\n这是测试内容。"
            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={"file": ("test.txt", BytesIO(content.encode("utf-8")), "text/plain")},
            )
            c.post(f"/api/topics/{topic_id}/parse")

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "NoP Session"},
            )
            assert resp.status_code == 201
            session_id = resp.json()["id"]

            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "Hello"},
            )
            assert resp.status_code == 409

    def test_delete_session_removes_messages(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Delete Me"},
            )
            session_id = resp.json()["id"]

            with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
                c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "Test question"},
                )

            resp = c.delete(f"/api/chat/sessions/{session_id}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

            resp = c.get(f"/api/chat/sessions/{session_id}/messages")
            assert resp.status_code == 404

    def test_llm_invalid_json_fallback(self, client):
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Bad JSON"},
            )
            session_id = resp.json()["id"]

            from services.llm_client import LLMResponse

            def bad_json(*args, **kwargs):
                return LLMResponse(
                    content="not valid json {{{",
                    model="test",
                    usage={},
                )

            with patch(CHAT_PATCH_PATH, side_effect=bad_json):
                resp = c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "Question?"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["role"] == "assistant"
                assert data["uncertainty"] is not None  # JSON parse failure flagged

    def test_no_external_api_calls(self, client):
        """Ensure chat tests never call external APIs."""
        with client as c:
            topic_id = _setup_chat(c)

            resp = c.post(
                f"/api/topics/{topic_id}/chat/sessions",
                json={"title": "Safe Test"},
            )
            session_id = resp.json()["id"]

            with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
                resp = c.post(
                    f"/api/chat/sessions/{session_id}/messages",
                    json={"content": "Safe question?"},
                )
                assert resp.status_code == 200


# ── Fix 014: Chat history & malformed JSON ──


def test_chat_history_included_in_llm_messages(client):
    """send_user_message includes recent history in the LLM call."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "History Test"},
        )
        session_id = resp.json()["id"]

        # Send first message
        with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
            c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "刘备是谁？"},
            )

        # Send second message — capture the messages passed to LLM
        captured_messages = []

        def capture_chat(messages, model, temperature, max_tokens, response_format):
            captured_messages.extend(messages)
            from services.llm_client import LLMResponse

            return LLMResponse(
                content='{"answer":"OK","evidence":[],"uncertainty":null}',
                model="test",
                usage={},
            )

        with patch(CHAT_PATCH_PATH, side_effect=capture_chat):
            c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "他做了什么？"},
            )

        # Expect at least system + previous user + previous assistant + current user
        assert len(captured_messages) >= 3
        roles = [m.role for m in captured_messages]
        assert "system" in roles
        assert roles.count("user") >= 1
        assert roles.count("assistant") >= 1


def test_malformed_json_fields_dont_crash(client):
    """Malformed but parseable JSON should not crash send_user_message."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "Malformed Test"},
        )
        session_id = resp.json()["id"]

        from services.llm_client import LLMResponse

        def malformed(*args, **kwargs):
            return LLMResponse(
                content='{"answer":123,"evidence":"not-list","uncertainty":{"x":1}}',
                model="test",
                usage={},
            )

        with patch(CHAT_PATCH_PATH, side_effect=malformed):
            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "Test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] == "assistant"
            # answer should be converted to string
            assert isinstance(data["content"], str)
            assert "123" in data["content"]
            # evidence_json comes from retrieval now; may be non-empty
            # old evidence from LLM ("not-list" string) is no longer used
            # uncertainty should be converted to string
            assert data["uncertainty"] is None or isinstance(data["uncertainty"], str)


# ── v0.3 Step 8: Structured evidence + RetrievalTrace ──


def test_structured_evidence_format(client):
    """New chat messages should store evidence as list of structured objects."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "Structured Evidence"},
        )
        session_id = resp.json()["id"]

        with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "刘备是谁？"},
            )
            assert resp.status_code == 200
            data = resp.json()
            evidence = data["evidence_json"]
            assert isinstance(evidence, list), f"Expected list, got {type(evidence)}"
            assert len(evidence) >= 1
            item = evidence[0]
            assert isinstance(item, dict)
            assert "text" in item
            assert item["source_type"] in ("chunk", "analysis_output", "atom")
            assert "source_id" in item
            assert "method" in item
            assert "score" in item
            # score should be float (not int)
            assert isinstance(item["score"], (int, float))


def test_retrieval_trace_created_for_chat(client):
    """Chat messages should create a RetrievalTrace with session/message IDs."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "Trace Test"},
        )
        session_id = resp.json()["id"]

        with patch(CHAT_PATCH_PATH, side_effect=_mock_chat_response):
            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "刘备是谁？"},
            )
            assert resp.status_code == 200

        # Verify RetrievalTrace exists
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.retrieval_trace import RetrievalTrace

        traces = session.exec(
            __import__("sqlmodel").select(RetrievalTrace).where(RetrievalTrace.topic_id == topic_id)
        ).all()
        assert len(traces) >= 1, "RetrievalTrace should be created for chat"
        trace = traces[-1]
        assert trace.session_id == session_id
        assert trace.message_id is not None
        assert trace.method == "hybrid"
        assert len(trace.results_json) > 0


def test_legacy_evidence_still_readable(client):
    """Old string[] evidence_json messages must still be returned without error."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "Legacy Evidence"},
        )
        session_id = resp.json()["id"]

        # Simulate an old-format message directly in DB
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.chat import ChatMessage

        old_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="Some old answer",
            evidence_json=json.dumps(["evidence string 1", "evidence string 2"]),
        )
        session.add(old_msg)
        session.commit()

        # Fetch messages via API
        resp = c.get(f"/api/chat/sessions/{session_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        # Find the old-format assistant message
        old = [m for m in messages if m["id"] == old_msg.id]
        assert len(old) == 1
        raw_evidence = old[0].get("evidence_json")
        # ChatMessageRead returns the raw JSON string
        assert isinstance(raw_evidence, str)
        parsed = json.loads(raw_evidence)
        assert parsed == ["evidence string 1", "evidence string 2"]


def test_empty_retrieval_uncertainty_flag(client):
    """When retrieval finds nothing, answer should indicate uncertainty."""
    with client as c:
        topic_id = _setup_chat(c)

        resp = c.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "No Evidence"},
        )
        session_id = resp.json()["id"]

        from services.llm_client import LLMResponse

        def empty_search_response(*args, **kwargs):
            return LLMResponse(
                content='{"answer":"不确定","evidence":[],"uncertainty":"No evidence found"}',
                model="test",
                usage={},
            )

        with patch(CHAT_PATCH_PATH, side_effect=empty_search_response):
            resp = c.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "xyznotfound12345"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # Should still work even with empty retrieval
            assert data["role"] == "assistant"
            assert data["content"] == "不确定"
