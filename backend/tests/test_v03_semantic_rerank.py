"""v0.3 Step 10 — Semantic Rerank tests."""

import io

from fastapi.testclient import TestClient


def _create_topic(client: TestClient, name: str = "Rerank Test") -> str:
    resp = client.post("/api/topics", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_and_parse(client: TestClient, topic_id: str, text: str) -> None:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", io.BytesIO(text.encode("utf-8")))},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(f"/api/topics/{topic_id}/parse")
    assert resp.status_code == 200, resp.text


# ── Semantic rerank disabled (default) ──


class TestSemanticRerankDisabled:
    def test_semantic_rerank_returns_warning(self, client):
        """When ENABLE_SEMANTIC_RERANK is False, requesting it returns a warning."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={
                "query": "quick fox",
                "methods": ["fts", "semantic_rerank"],
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None, "Should return warning when semantic_rerank is disabled"
        assert "disabled" in data["warning"].lower()
        # Results should still be returned (from fts)
        assert len(data["results"]) >= 1

    def test_semantic_rerank_only_returns_warning_and_422(self, client):
        """semantic_rerank alone with no retrieval method should be rejected."""
        topic_id = _create_topic(client)

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={
                "query": "hello",
                "methods": ["semantic_rerank"],
                "top_k": 5,
            },
        )
        assert resp.status_code == 422

    def test_default_no_rerank_no_warning(self, client):
        """Without semantic_rerank in methods, no warning should appear."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is None


# ── Existing tests must not regress ──


class TestNoRegression:
    def test_basic_retrieve_unchanged(self, client):
        """Standard retrieve (no semantic_rerank) must work exactly as before."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n刘备和曹操相遇于赤壁。\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "刘备", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["trace_id"] is None
        assert data["warning"] is None
        for r in data["results"]:
            assert r["source_type"] in ("chunk", "analysis_output", "atom")

    def test_persist_trace_still_works(self, client):
        """persist_trace with semantic_rerank should still persist trace."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={
                "query": "quick fox",
                "methods": ["fts", "semantic_rerank"],
                "top_k": 5,
                "persist_trace": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_id"] is not None
        assert data["warning"] is not None

    def test_valid_method_accepted(self, client):
        """semantic_rerank should be accepted as a valid method string."""
        topic_id = _create_topic(client)

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={
                "query": "hello",
                "methods": ["fts", "semantic_rerank"],
                "top_k": 5,
            },
        )
        # Even though the topic has no chunks, 422 should NOT be from invalid method
        # It can be 200 (empty results) or 404 (topic not found)
        assert resp.status_code in (200, 404)


# ── Embedding service unit tests ──


class TestEmbeddingService:
    def test_semantic_rerank_returns_unchanged_when_disabled(self):
        from services.embedding_service import semantic_rerank

        candidates = [
            {"source_type": "chunk", "source_id": "c1", "score": 1.0},
            {"source_type": "chunk", "source_id": "c2", "score": 0.5},
        ]
        result, warning = semantic_rerank(candidates, "test query", "topic-1")
        assert result == candidates, "Candidates should be unchanged when rerank is disabled"
        assert warning is not None
        assert "disabled" in warning.lower()

    def test_embedding_provider_is_skeleton(self):
        from services.embedding_service import EmbeddingProvider

        p = EmbeddingProvider("http://localhost", "sk-key", "model")
        try:
            p.embed(["test"])
            assert False, "Should have raised NotImplementedError"
        except NotImplementedError:
            pass
