from sqlmodel import Session

from models.chunk import Chunk
from services import retrieval_service


def _add_chunk(
    session: Session,
    topic_id: str,
    doc_id: str,
    chunk_index: int,
    text: str,
    chapter_index: int = 0,
) -> None:
    chunk = Chunk(
        topic_id=topic_id,
        document_id=doc_id,
        chunk_index=chunk_index,
        chapter_index=chapter_index,
        text=text,
        start_char=0,
        end_char=len(text),
        char_count=len(text),
        estimated_tokens=max(1, len(text) // 2),
    )
    session.add(chunk)
    session.commit()


class TestRetrievalService:
    def test_keyword_match_chunks(self, client):
        with client as c:
            # Setup
            resp = c.post("/api/topics", json={"name": "RT"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={
                    "file": (
                        "test.txt",
                        BytesIO("刘备与关羽张飞在桃园结义。\n".encode("utf-8")),
                        "text/plain",
                    )
                },
            )
            c.post(f"/api/topics/{topic_id}/parse")

            # Get session for direct service call
            from db import get_session
            from main import app

            session = next(app.dependency_overrides.get(get_session, get_session)())

            results = retrieval_service.retrieve_chunks(topic_id, "刘备", session, top_k=5)
            assert len(results) > 0
            assert any("刘备" in r["text_excerpt"] for r in results)

    def test_chinese_substring_match(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "R2"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={
                    "file": (
                        "test.txt",
                        BytesIO("曹操率军南下，欲取江南。\n".encode("utf-8")),
                        "text/plain",
                    )
                },
            )
            c.post(f"/api/topics/{topic_id}/parse")

            from db import get_session
            from main import app

            session_gen = app.dependency_overrides.get(get_session, get_session)
            session = next(session_gen())

            results = retrieval_service.retrieve_chunks(topic_id, "曹操", session, top_k=5)
            assert len(results) > 0
            assert any("曹操" in r["text_excerpt"] for r in results)

    def test_top_k_limit(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "R3"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            text = ""
            for i in range(10):
                text += f"第{i}章 这是关于刘备的故事。\n"
            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={
                    "file": (
                        "test.txt",
                        BytesIO(text.encode("utf-8")),
                        "text/plain",
                    )
                },
            )
            c.post(f"/api/topics/{topic_id}/parse")

            from db import get_session
            from main import app

            session_gen = app.dependency_overrides.get(get_session, get_session)
            session = next(session_gen())

            results = retrieval_service.retrieve_chunks(topic_id, "刘备", session, top_k=3)
            assert len(results) <= 3

    def test_no_match_returns_empty(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "R4"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={
                    "file": (
                        "test.txt",
                        BytesIO("Hello world.\n".encode("utf-8")),
                        "text/plain",
                    )
                },
            )
            c.post(f"/api/topics/{topic_id}/parse")

            from db import get_session
            from main import app

            session_gen = app.dependency_overrides.get(get_session, get_session)
            session = next(session_gen())

            results = retrieval_service.retrieve_chunks(topic_id, "XYZNOTFOUND", session, top_k=5)
            assert len(results) == 0

    def test_analysis_output_hit(self, client):
        with client as c:
            resp = c.post("/api/topics", json={"name": "R5"})
            topic_id = resp.json()["id"]

            from io import BytesIO

            c.post(
                f"/api/topics/{topic_id}/documents/upload",
                files={
                    "file": (
                        "test.txt",
                        BytesIO("第一章\n曹操出场。\n".encode("utf-8")),
                        "text/plain",
                    )
                },
            )
            c.post(f"/api/topics/{topic_id}/parse")

            # Create a provider for analysis
            c.post(
                "/api/model-providers",
                json={
                    "name": "R5P",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-key",
                    "model_name": "m",
                    "is_default": True,
                },
            )

            # Run analysis with mock
            from unittest.mock import patch

            with patch(
                "services.analysis_service.OpenAICompatibleLLMClient.chat",
                side_effect=_mock_retrieval_analysis,
            ):
                c.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=3")

            from db import get_session
            from main import app

            session_gen = app.dependency_overrides.get(get_session, get_session)
            session = next(session_gen())

            results = retrieval_service.retrieve_analysis(topic_id, "曹操", session, top_k=5)
            assert len(results) > 0
            assert any("曹操" in r.get("content_excerpt", "") for r in results)


def _mock_retrieval_analysis(messages, model, temperature, max_tokens, response_format):
    from services.llm_client import LLMResponse

    return LLMResponse(
        content='{"title":"Test","characters":[{"name":"曹操"}],"source_chunk_ids":[],"evidence_quotes":["曹操出场。"],"confidence":0.9}',
        model="test",
        usage={},
    )
