"""Tests for enhanced chunks/meta and analysis_selection_service."""

import io

import pytest
from sqlmodel import Session
from sqlmodel import select as sql_select

from models.chunk import Chunk
from models.enums import AnalysisMode
from services.analysis_selection_service import (
    estimate_v2_analysis_cost,
    select_chunks_for_analysis,
    validate_analysis_mode,
)


def _setup(client):
    """Create topic + upload + parse. Returns topic_id."""
    r = client.post("/api/topics", json={"name": "Selection Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    content = io.BytesIO("第一章 测试\n内容。\n第二章 更多\n内。\n".encode())
    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", content, "text/plain")},
    )
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200
    return topic_id


# ── Chunks meta endpoint ──


def test_chunks_meta_basic(client):
    topic_id = _setup(client)
    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    assert r.status_code == 200
    data = r.json()
    assert data["chunk_count"] > 0
    assert data["chapter_count"] > 0
    assert "document_id" in data
    assert "first_chunk_index" in data
    assert "first_global_chunk_index" in data
    assert "last_global_chunk_index" in data
    assert data["first_global_chunk_index"] == 0
    assert data["last_global_chunk_index"] == data["chunk_count"] - 1
    client.delete(f"/api/topics/{topic_id}")


def test_chunks_meta_per_chapter(client):
    topic_id = _setup(client)
    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    assert r.status_code == 200
    data = r.json()
    by_chapter = data["chunks_by_chapter"]
    assert isinstance(by_chapter, list)
    assert len(by_chapter) >= 1
    for ch in by_chapter:
        assert "chapter_index" in ch
        assert "title" in ch
        assert "chunk_count" in ch
        assert ch["chunk_count"] > 0
    client.delete(f"/api/topics/{topic_id}")


def test_chunks_meta_unparsed_409(client):
    r = client.post("/api/topics", json={"name": "Unparsed"})
    assert r.status_code == 201
    topic_id = r.json()["id"]
    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章\n".encode()), "text/plain")},
    )
    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_chunks_meta_no_document_404(client):
    r = client.post("/api/topics", json={"name": "No Doc"})
    assert r.status_code == 201
    topic_id = r.json()["id"]
    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    assert r.status_code == 404
    client.delete(f"/api/topics/{topic_id}")


# ── Chunk selection ──


def test_select_preview(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.PREVIEW, limit_chunks=2
        )
        assert len(chunks) <= 2
        assert info["mode"] == "preview"
    client.delete(f"/api/topics/{topic_id}")


def test_select_preview_default_limit(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.PREVIEW)
        assert len(chunks) > 0
        assert info["limit_chunks"] is not None
    client.delete(f"/api/topics/{topic_id}")


def test_select_preview_limit_zero_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="limit_chunks"):
            select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.PREVIEW, limit_chunks=0)
    client.delete(f"/api/topics/{topic_id}")


def test_select_full(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.FULL)
        assert len(chunks) > 0
        assert info["selected"] == info["total"]
    client.delete(f"/api/topics/{topic_id}")


def test_select_full_with_safety_cap(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.FULL, safety_cap=1
        )
        assert len(chunks) == 1
        assert info.get("capped") is True
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_by_chapter(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.RANGE, chapter_start=0, chapter_end=0
        )
        for c in chunks:
            assert c.chapter_index == 0
        assert info["mode"] == "range"
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_no_params_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="Range mode requires"):
            select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.RANGE)
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_start_gt_end_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="range_start.*greater"):
            select_chunks_for_analysis(
                session, topic_id, mode=AnalysisMode.RANGE, range_start=5, range_end=1
            )
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_both_ranges_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="both"):
            select_chunks_for_analysis(
                session,
                topic_id,
                mode=AnalysisMode.RANGE,
                range_start=0,
                range_end=1,
                chapter_start=0,
                chapter_end=1,
            )
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_negative_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="negative"):
            select_chunks_for_analysis(
                session, topic_id, mode=AnalysisMode.RANGE, range_start=-1, range_end=1
            )
    client.delete(f"/api/topics/{topic_id}")


def test_select_range_chapter_start_gt_end_raises(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="chapter_start.*greater"):
            select_chunks_for_analysis(
                session, topic_id, mode=AnalysisMode.RANGE, chapter_start=5, chapter_end=1
            )
    client.delete(f"/api/topics/{topic_id}")


def test_select_incremental_no_previous(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.INCREMENTAL)
        assert len(chunks) > 0
        assert info["fallback"] == "no_previous_run"
    client.delete(f"/api/topics/{topic_id}")


def test_select_incremental_with_run_id(client, engine):
    """incremental with a real run skips succeeded chunks."""
    topic_id = _setup(client)
    from models.analysis_run import AnalysisRun
    from models.local_extraction import LocalExtraction

    all_chunks = client.get(f"/api/topics/{topic_id}/chunks?limit=10").json()["chunks"]
    assert len(all_chunks) >= 2

    run_id_to_use: str = ""
    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id, mode=AnalysisMode.PREVIEW)
        session.add(run)
        session.flush()
        run_id_to_use = run.id
        ext = LocalExtraction(
            run_id=run.id,
            topic_id=topic_id,
            chunk_id=all_chunks[0]["id"],
            status="succeeded",
            attempt_count=1,
        )
        session.add(ext)
        session.commit()

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.INCREMENTAL, incremental_run_id=run_id_to_use
        )
        chunk_ids = [c.id for c in chunks]
        assert all_chunks[0]["id"] not in chunk_ids
        assert all_chunks[1]["id"] in chunk_ids
        assert info["base_run_id"] == run_id_to_use
    client.delete(f"/api/topics/{topic_id}")


def test_select_incremental_run_not_found(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="AnalysisRun not found"):
            select_chunks_for_analysis(
                session,
                topic_id,
                mode=AnalysisMode.INCREMENTAL,
                incremental_run_id="nonexistent-id",
            )
    client.delete(f"/api/topics/{topic_id}")


def test_select_incremental_cross_topic_raises(client, engine):
    """incremental_run_id from topic A cannot be used on topic B."""
    topic_a = _setup(client)
    topic_b = _setup(client)

    from models.analysis_run import AnalysisRun

    with Session(engine) as session:
        run_a = AnalysisRun(topic_id=topic_a, mode=AnalysisMode.PREVIEW)
        session.add(run_a)
        session.commit()
        run_a_id = run_a.id

    with Session(engine) as session:
        with pytest.raises(ValueError, match="does not belong to this topic"):
            select_chunks_for_analysis(
                session, topic_b, mode=AnalysisMode.INCREMENTAL, incremental_run_id=run_a_id
            )
    client.delete(f"/api/topics/{topic_a}")
    client.delete(f"/api/topics/{topic_b}")


def test_validate_analysis_mode():
    validate_analysis_mode("preview")
    validate_analysis_mode("full")
    with pytest.raises(ValueError):
        validate_analysis_mode("invalid_mode")


def test_validate_analysis_mode_v1_types_rejected():
    with pytest.raises(ValueError):
        validate_analysis_mode("overview")


def test_cost_estimate_preview(client, engine):
    topic_id = _setup(client)
    with Session(engine) as session:
        chunks, _ = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.PREVIEW, limit_chunks=2
        )
        est = estimate_v2_analysis_cost(chunks, ["characters", "events"])
        assert est["selected_chunk_count"] <= 2
        assert est["estimated_total_input_tokens"] > 0
        assert "estimated_final_input_total" in est
    client.delete(f"/api/topics/{topic_id}")


def test_cost_estimate_no_chunks():
    est = estimate_v2_analysis_cost([])
    assert est["selected_chunk_count"] == 0
    assert est["estimated_total_input_tokens"] == 0


def _make_test_chunks(n: int) -> list:
    from models.chunk import Chunk
    return [
        Chunk(
            topic_id="t1", document_id="d1", chunk_index=i,
            text="test text here",
            start_char=i * 100, end_char=(i + 1) * 100,
            char_count=2000, estimated_tokens=1333,
        )
        for i in range(n)
    ]


def test_cost_estimate_uses_max_output_tokens():
    """Output estimate should scale with max_output_tokens, not fixed 2048."""
    chunks = _make_test_chunks(5)
    est_default = estimate_v2_analysis_cost(chunks)
    est_high = estimate_v2_analysis_cost(chunks, max_output_tokens=8192)
    est_low = estimate_v2_analysis_cost(chunks, max_output_tokens=2048)
    # Higher max_output_tokens → higher output estimate
    assert est_high["estimated_total_output_tokens"] > est_low["estimated_total_output_tokens"]
    # Default (4096) output should be between high and low
    assert est_high["estimated_total_output_tokens"] > est_default["estimated_total_output_tokens"]
    # Final stages should be 0 (deterministic Python, not LLM)
    assert est_default["estimated_final_output_total"] == 0
    assert est_default["estimated_merge_input_tokens"] == 0


def test_cost_estimate_thinking_mode_increases_output():
    """Thinking mode enabled should produce higher output estimate."""
    chunks = _make_test_chunks(3)
    est_disabled = estimate_v2_analysis_cost(chunks, thinking_mode="disabled")
    est_enabled = estimate_v2_analysis_cost(chunks, thinking_mode="enabled")
    assert est_enabled["estimated_total_output_tokens"] > est_disabled["estimated_total_output_tokens"]


def test_cost_estimate_retry_multiplier_affects_output():
    """Higher retry multiplier → higher output estimate."""
    chunks = _make_test_chunks(1)
    est_no_retry = estimate_v2_analysis_cost(chunks, retry_multiplier=1.0)
    est_with_retry = estimate_v2_analysis_cost(chunks, retry_multiplier=1.5)
    assert est_with_retry["estimated_total_output_tokens"] > est_no_retry["estimated_total_output_tokens"]


def test_cost_estimate_final_stages_zero_llm_cost():
    """Merge and final stages should be 0 (deterministic Python, no LLM)."""
    chunks = _make_test_chunks(1)
    est = estimate_v2_analysis_cost(chunks, requested_types=["characters", "events"])
    assert est["estimated_merge_input_tokens"] == 0
    assert est["estimated_final_input_total"] == 0
    assert est["estimated_final_output_total"] == 0


def test_cost_estimate_mode_affects_retry_multiplier():
    """Preview mode → 1.15 retry; full mode → 1.25 retry; full should be higher."""
    chunks = _make_test_chunks(3)
    est_preview = estimate_v2_analysis_cost(chunks, mode="preview")
    est_full = estimate_v2_analysis_cost(chunks, mode="full")
    # Same output_per_chunk, different retry multipliers
    assert est_full["estimated_total_output_tokens"] > est_preview["estimated_total_output_tokens"]


def test_cost_estimate_incremental_same_as_preview():
    """Incremental should use same 1.15 multiplier as preview."""
    chunks = _make_test_chunks(3)
    est_preview = estimate_v2_analysis_cost(chunks, mode="preview")
    est_incremental = estimate_v2_analysis_cost(chunks, mode="incremental")
    assert est_preview["estimated_total_output_tokens"] == est_incremental["estimated_total_output_tokens"]


def test_no_chunks_returns_empty_list(client, engine):
    r = client.post("/api/topics", json={"name": "No Chunks"})
    topic_id = r.json()["id"]
    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(session, topic_id, mode=AnalysisMode.FULL)
        assert chunks == []
        assert info["selected"] == 0
    client.delete(f"/api/topics/{topic_id}")


def test_range_mode_uses_global_index_not_chapter_local(client, engine):
    """Range mode with chunk_index_start/end selects by global ordinal, not per-chapter."""
    import io as _io

    r = client.post("/api/topics", json={"name": "MultiCh Range"})
    tid = r.json()["id"]
    # Two chapters, each should have at least 1 chunk
    content = "第一章 测试\n" + "内容。\n" * 50 + "\n第二章 更多\n" + "测试。\n" * 50
    client.post(
        f"/api/topics/{tid}/documents/upload",
        files={"file": ("n.txt", _io.BytesIO(content.encode()), "text/plain")},
    )
    client.post(f"/api/topics/{tid}/parse")

    with Session(engine) as session:
        all_chunks: list = session.exec(
            sql_select(Chunk)
            .where(Chunk.topic_id == tid)
            .order_by(Chunk.chapter_index, Chunk.chunk_index)
        ).all()  # noqa: E501
        assert len(all_chunks) >= 2

        # Select global indices 1..2 (second and third chunks across the whole document)
        chunks, info = select_chunks_for_analysis(
            session, tid, mode=AnalysisMode.RANGE, range_start=1, range_end=2
        )
        assert info["mode"] == "range"
        # Selected chunks should be global indices 1 and 2
        assert len(chunks) >= 1
        selected_ids = {c.id for c in chunks}
        expected_ids = {all_chunks[i].id for i in range(1, min(3, len(all_chunks)))}
        assert selected_ids == expected_ids

    client.delete(f"/api/topics/{tid}")
