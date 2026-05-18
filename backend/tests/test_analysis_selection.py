"""Tests for enhanced chunks/meta and analysis_selection_service."""

import io

from models.enums import AnalysisMode
from services.analysis_selection_service import (
    estimate_v2_analysis_cost,
    select_chunks_for_analysis,
    validate_analysis_mode,
)


def _setup_topic(client):
    """Create topic + upload + parse. Returns topic_id."""
    r = client.post("/api/topics", json={"name": "Selection Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={
            "file": (
                "novel.txt",
                io.BytesIO("第一章 测试\n内容。\n第二章 更多\n内。\n第三章 结束\n。\n".encode()),
                "text/plain",
            )
        },
    )
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200
    return topic_id


# ── Chunks meta endpoint ──


def test_chunks_meta_basic(client):
    """GET /api/topics/{id}/chunks/meta returns extended metadata."""
    topic_id = _setup_topic(client)

    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    assert r.status_code == 200
    data = r.json()

    assert data["chunk_count"] > 0
    assert data["chapter_count"] > 0
    assert data["total_chars"] > 0
    assert data["estimated_tokens"] > 0
    assert "first_chunk_index" in data
    assert "last_chunk_index" in data

    client.delete(f"/api/topics/{topic_id}")


def test_chunks_meta_per_chapter(client):
    """chunks/meta includes per-chapter breakdown."""
    topic_id = _setup_topic(client)

    r = client.get(f"/api/topics/{topic_id}/chunks/meta")
    data = r.json()

    by_chapter = data["chunks_by_chapter"]
    assert isinstance(by_chapter, list)
    assert len(by_chapter) >= 1
    for ch in by_chapter:
        assert "chapter_index" in ch
        assert "title" in ch
        assert "chunk_count" in ch
        assert "char_count" in ch
        assert ch["chunk_count"] > 0

    client.delete(f"/api/topics/{topic_id}")


def test_chunks_meta_404(client):
    """Nonexistent topic returns 404."""
    r = client.get("/api/topics/nonexistent-id/chunks/meta")
    assert r.status_code == 404


# ── Chunk selection ──


def test_select_preview(client, engine):
    """Preview mode selects a limited subset of chunks."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.PREVIEW, limit_chunks=2
        )
        assert len(chunks) <= 2
        assert info["mode"] == "preview"
        assert info["selected"] <= 2

    client.delete(f"/api/topics/{topic_id}")


def test_select_preview_default_limit(client, engine):
    """Preview with no limit_chunks uses recommended default."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.PREVIEW
        )
        assert len(chunks) > 0
        assert info["limit_chunks"] is not None

    client.delete(f"/api/topics/{topic_id}")


def test_select_full(client, engine):
    """Full mode selects all chunks."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.FULL
        )
        assert len(chunks) > 0
        assert info["selected"] == info["total"]

    client.delete(f"/api/topics/{topic_id}")


def test_select_range_by_chapter(client, engine):
    """Range mode with chapter boundaries selects correct subset."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.RANGE, chapter_start=0, chapter_end=0
        )
        for c in chunks:
            assert c.chapter_index == 0
        assert info["mode"] == "range"

    client.delete(f"/api/topics/{topic_id}")


def test_select_range_by_chunk_index(client, engine):
    """Range mode with chunk index boundaries selects correct subset."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.RANGE, range_start=0, range_end=1
        )
        assert info["mode"] == "range"

    client.delete(f"/api/topics/{topic_id}")


def test_select_incremental_no_previous_run(client, engine):
    """Incremental with no previous runs falls back to full."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.INCREMENTAL
        )
        assert len(chunks) > 0
        assert info["fallback"] == "no_previous_run"

    client.delete(f"/api/topics/{topic_id}")


def test_validate_analysis_mode():
    """Valid modes pass, invalid raise ValueError."""
    validate_analysis_mode("preview")
    validate_analysis_mode("full")
    try:
        validate_analysis_mode("invalid_mode")
        assert False, "Should have raised"
    except ValueError:
        pass


def test_validate_analysis_mode_v1_types_rejected():
    """Old v1 analysis types are not valid v2 modes."""
    try:
        validate_analysis_mode("overview")
        assert False, "Should have raised"
    except ValueError:
        pass


# ── Cost estimation ──


def test_cost_estimate_preview(client, engine):
    """Cost estimation for preview mode returns structured estimate."""
    topic_id = _setup_topic(client)
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, _info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.PREVIEW, limit_chunks=2
        )
        estimate = estimate_v2_analysis_cost(chunks, ["characters", "events"])
        assert estimate["selected_chunk_count"] <= 2
        assert estimate["estimated_total_input_tokens"] > 0
        assert estimate["estimated_total_output_tokens"] > 0
        assert len(estimate["estimate_notes"]) > 0

    client.delete(f"/api/topics/{topic_id}")


def test_cost_estimate_no_chunks():
    """Cost estimation with no chunks returns zeros."""
    estimate = estimate_v2_analysis_cost([])
    assert estimate["selected_chunk_count"] == 0
    assert estimate["estimated_total_input_tokens"] == 0


def test_no_chunks_returns_empty_list(client, engine):
    """Selecting chunks for a topic with no chunks returns empty list."""
    r = client.post("/api/topics", json={"name": "No Chunks Topic"})
    topic_id = r.json()["id"]
    from sqlmodel import Session

    with Session(engine) as session:
        chunks, info = select_chunks_for_analysis(
            session, topic_id, mode=AnalysisMode.FULL
        )
        assert chunks == []
        assert info["selected"] == 0

    client.delete(f"/api/topics/{topic_id}")
