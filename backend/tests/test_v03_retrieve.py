"""v0.3 Step 7 — Hybrid retrieval + RetrievalTrace tests."""

import io
import json

from fastapi.testclient import TestClient


def _create_topic(client: TestClient, name: str = "Retrieve Test") -> str:
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


VALID_METHOD_NAMES = {"fts", "keyword_fallback", "structured", "analysis_output"}


def _assert_valid_method(method: str) -> None:
    """Method may be combined like 'fts+keyword_fallback'; each part must be valid."""
    for part in method.split("+"):
        assert part in VALID_METHOD_NAMES, f"Invalid method part: {part}"


def _create_minimal_run(session, topic_id: str) -> str:
    """Create a minimal AnalysisRun and return its ID (needed for atom FK)."""
    from models.analysis_run import AnalysisRun

    run = AnalysisRun(topic_id=topic_id)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run.id


# ── Retrieve API ──


class TestRetrieveAPI:
    def test_basic_retrieve_returns_candidates(self, client):
        """Retrieve should return ranked candidates with required fields."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps over the lazy dog.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick fox", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "quick fox"
        assert data["trace_id"] is None
        assert len(data["results"]) >= 1

        for r in data["results"]:
            assert r["source_type"] in ("chunk", "analysis_output", "atom")
            assert "source_id" in r
            assert "title" in r
            assert "snippet" in r
            assert isinstance(r["score"], (int, float))
            _assert_valid_method(r["method"])
            assert isinstance(r["matched_terms"], list)
            if r["source_type"] == "chunk":
                assert r["chunk_id"] is not None

    def test_cjk_retrieve(self, client):
        """Retrieve should work for CJK queries."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n刘备和曹操相遇于赤壁。\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "刘备曹操", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1

    def test_no_results(self, client):
        """Retrieve should return empty results for non-matching queries."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nHello world.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "xyznonexistent12345", "top_k": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_filter_by_methods(self, client):
        """Retrieve should honor the methods filter."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick", "methods": ["fts"], "top_k": 5},
        )
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["method"] == "fts"

    def test_persist_trace(self, client):
        """persist_trace=True should create a RetrievalTrace and return its ID."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick fox", "top_k": 5, "persist_trace": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_id"] is not None, "persist_trace=True should return a trace_id"

        # Verify trace is retrievable from DB
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())
        from models.retrieval_trace import RetrievalTrace

        trace = session.get(RetrievalTrace, data["trace_id"])
        assert trace is not None
        assert trace.topic_id == topic_id
        assert trace.query == "quick fox"
        assert trace.method == "hybrid"
        results = json.loads(trace.results_json)
        assert isinstance(results, list)
        assert len(results) >= 1
        assert "score" in results[0]
        # Snippets should be truncated to ≤200 chars
        for r in results:
            assert len(r.get("snippet", "")) <= 200

    # ── Validation ──

    def test_empty_query_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "", "top_k": 5},
        )
        assert resp.status_code == 422

    def test_whitespace_query_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "   ", "top_k": 5},
        )
        assert resp.status_code == 422

    def test_missing_query_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"top_k": 5},
        )
        assert resp.status_code == 422

    def test_invalid_methods_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "hello", "methods": ["invalid_method"], "top_k": 5},
        )
        assert resp.status_code == 422

    def test_empty_methods_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "hello", "methods": [], "top_k": 5},
        )
        assert resp.status_code == 422

    def test_top_k_out_of_range_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "hello", "top_k": 0},
        )
        assert resp.status_code == 422

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "hello", "top_k": 51},
        )
        assert resp.status_code == 422

    def test_topic_not_found_404(self, client):
        resp = client.post(
            "/api/topics/nonexistent-id/retrieve",
            json={"query": "hello", "top_k": 5},
        )
        assert resp.status_code == 404

    def test_top_k_limit(self, client):
        """Results should respect top_k limit."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n" + "quick " * 50 + "\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick", "top_k": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 2


# ── Structured (Atom) retrieval ──


class TestStructuredRetrieval:
    def test_atom_search_by_canonical_name(self, client):
        """Retrieve should find atoms by canonical_name."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n刘备和关羽在桃园结义。\n")

        # Insert an atom directly
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.extracted_atom import ExtractedAtom

        run_id = _create_minimal_run(session, topic_id)

        atom = ExtractedAtom(
            topic_id=topic_id,
            run_id=run_id,
            atom_type="character",
            stable_id="char_liubei",
            canonical_name="刘备",
            title="刘玄德",
            content_json=json.dumps({"aliases": ["玄德", "刘皇叔"], "role": "主角"}),
            evidence_quotes=json.dumps(["刘备出场。", "刘备与关羽结义。"]),
            source_chunk_ids="[]",
            confidence=0.9,
        )
        session.add(atom)
        session.commit()

        # Search by canonical name
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "刘备", "methods": ["structured"], "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any(r["source_type"] == "atom" for r in results)
        atom_results = [r for r in results if r["source_type"] == "atom"]
        assert any("刘备" in r["title"] or "刘备" in r["snippet"] for r in atom_results)

    def test_atom_search_by_alias(self, client):
        """Retrieve should find atoms by aliases stored in content_json."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n诸葛亮出场。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.extracted_atom import ExtractedAtom

        run_id = _create_minimal_run(session, topic_id)

        atom = ExtractedAtom(
            topic_id=topic_id,
            run_id=run_id,
            atom_type="character",
            stable_id="char_zhugeliang",
            canonical_name="诸葛亮",
            title="诸葛孔明",
            content_json=json.dumps({"aliases": ["孔明", "卧龙"]}),
            evidence_quotes=json.dumps(["诸葛亮出场。"]),
            source_chunk_ids="[]",
            confidence=0.9,
        )
        session.add(atom)
        session.commit()

        # Search by alias
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "卧龙", "methods": ["structured"], "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        atom_results = [r for r in results if r["source_type"] == "atom"]
        assert len(atom_results) >= 1

    def test_atom_search_by_evidence(self, client):
        """Retrieve should find atoms by evidence_quotes content."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n赤壁之战，火烧连环船。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.extracted_atom import ExtractedAtom

        run_id = _create_minimal_run(session, topic_id)

        atom = ExtractedAtom(
            topic_id=topic_id,
            run_id=run_id,
            atom_type="event",
            stable_id="event_chibi",
            canonical_name="赤壁之战",
            title="赤壁之战",
            content_json=json.dumps({"aliases": ["火烧赤壁"]}),
            evidence_quotes=json.dumps(["火烧连环船", "东南风大起"]),
            source_chunk_ids="[]",
            confidence=0.9,
        )
        session.add(atom)
        session.commit()

        # Search by evidence quote text
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "连环船", "methods": ["structured"], "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        atom_results = [r for r in results if r["source_type"] == "atom"]
        assert len(atom_results) >= 1


# ── Analysis output retrieval ──


class TestAnalysisOutputRetrieval:
    def test_output_search(self, client):
        """Retrieve should find analysis outputs by content."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n曹操率军南下，欲取江南。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.analysis_output import AnalysisOutput

        output = AnalysisOutput(
            topic_id=topic_id,
            output_type="characters",
            title="曹操",
            content_json=json.dumps({"name": "曹操", "role": "奸雄", "description": "曹操是三国时期的重要人物"}),
            source_chunk_ids="[]",
            evidence_quotes=json.dumps(["曹操率军南下"]),
            confidence=0.9,
        )
        session.add(output)
        session.commit()

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "曹操", "methods": ["analysis_output"], "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        output_results = [r for r in results if r["source_type"] == "analysis_output"]
        assert len(output_results) >= 1
        assert any("曹操" in r["title"] for r in output_results)

    def test_output_search_no_match(self, client):
        """analysis_output method should return empty when no outputs match."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nHello world.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "xyznonexistent", "methods": ["analysis_output"], "top_k": 5},
        )
        assert resp.status_code == 200
        output_results = [r for r in resp.json()["results"] if r["source_type"] == "analysis_output"]
        assert len(output_results) == 0


# ── Dedup & normalization ──


class TestDedupAndNormalization:
    def test_no_duplicate_chunks(self, client):
        """Same chunk should not appear multiple times even if matched by multiple methods."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps over the lazy dog.\n")

        # Use both fts and keyword_fallback — same chunk may match both
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick fox", "methods": ["fts", "keyword_fallback"], "top_k": 10},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        chunk_ids = [r["chunk_id"] for r in results if r.get("chunk_id")]
        # No duplicate chunk_ids
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_scores_normalized(self, client):
        """Scores should be normalized to [0, 1] range when multiple results exist."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps over the lazy dog.\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "quick", "top_k": 10},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        if len(results) > 1:
            scores = [r["score"] for r in results]
            assert all(0.0 <= s <= 1.0 for s in scores), f"Scores out of [0,1] range: {scores}"
            assert max(scores) == 1.0, "Top result should have score 1.0"
        elif len(results) == 1:
            assert results[0]["score"] in (0.0, 1.0)


# ── Hybrid retrieval with multiple methods ──


class TestHybridMultiMethod:
    def test_all_methods_combined(self, client):
        """Using all methods should combine results from multiple sources."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\n曹操和刘备在许昌会面，讨论天下大势。\n")

        # Create an atom and an output
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.analysis_output import AnalysisOutput
        from models.extracted_atom import ExtractedAtom

        run_id = _create_minimal_run(session, topic_id)

        atom = ExtractedAtom(
            topic_id=topic_id,
            run_id=run_id,
            atom_type="character",
            stable_id="char_caocao",
            canonical_name="曹操",
            title="曹孟德",
            content_json=json.dumps({"aliases": ["曹丞相"]}),
            evidence_quotes=json.dumps(["曹操在许昌"]),
            source_chunk_ids="[]",
            confidence=0.9,
        )
        session.add(atom)

        output = AnalysisOutput(
            topic_id=topic_id,
            output_type="characters",
            title="曹操",
            content_json=json.dumps({"name": "曹操", "description": "曹操登场"}),
            source_chunk_ids="[]",
            evidence_quotes=json.dumps(["曹操和刘备在许昌会面"]),
            confidence=0.9,
        )
        session.add(output)
        session.commit()

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "曹操", "top_k": 10},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        # Should have results from multiple source types
        types = {r["source_type"] for r in results}
        assert len(types) >= 2, f"Expected >= 2 source types, got {types}"

    def test_hybrid_dedup_across_chunk_sources(self, client):
        """FTS + keyword should not duplicate the same chunk."""
        topic_id = _create_topic(client)
        # Create enough text to have CJK content so both FTS and keyword fire
        _upload_and_parse(client, topic_id, "第一章\n\n刘备与关羽张飞在桃园结义。三人誓言同生共死。\n")

        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "刘备", "methods": ["fts", "keyword_fallback"], "top_k": 10},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        chunk_results = [r for r in results if r["source_type"] == "chunk"]
        chunk_ids = [r["chunk_id"] for r in chunk_results]
        assert len(chunk_ids) == len(set(chunk_ids)), "Chunks should not be duplicated"


# ── Legacy service backward compatibility ──


class TestLegacyRetrievalService:
    def test_retrieve_chunks_still_works(self, client):
        """Legacy retrieve_chunks() must not regress."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "刘备与关羽张飞在桃园结义。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from services.retrieval_service import retrieve_chunks

        results = retrieve_chunks(topic_id, "刘备", session, top_k=5)
        assert len(results) > 0
        assert "chunk_id" in results[0]
        assert "text_excerpt" in results[0]
        assert "score" in results[0]

    def test_retrieve_analysis_still_works(self, client):
        """Legacy retrieve_analysis() must not regress."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "曹操率军南下。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from models.analysis_output import AnalysisOutput
        from services.retrieval_service import retrieve_analysis

        output = AnalysisOutput(
            topic_id=topic_id,
            output_type="characters",
            title="曹操",
            content_json=json.dumps({"name": "曹操"}),
            source_chunk_ids="[]",
            evidence_quotes=json.dumps(["曹操率军南下"]),
            confidence=0.9,
        )
        session.add(output)
        session.commit()

        results = retrieve_analysis(topic_id, "曹操", session, top_k=5)
        assert len(results) > 0
        assert "output_id" in results[0]
        assert "content_excerpt" in results[0]

    def test_build_evidence_context_still_works(self, client):
        """Legacy build_evidence_context() must not regress."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "刘备与关羽张飞在桃园结义。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from services.retrieval_service import build_evidence_context

        ctx = build_evidence_context(topic_id, "刘备", session)
        assert "chunks" in ctx
        assert "analysis_outputs" in ctx
        assert len(ctx["chunks"]) > 0
