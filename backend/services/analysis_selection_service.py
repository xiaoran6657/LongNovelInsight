"""Chunk selection for v0.2 analysis modes and cost estimation.

Pure Python service — no LLM calls, no DB writes.
"""

from sqlmodel import Session, select

from models.chunk import Chunk
from models.document import Document
from models.enums import AnalysisMode

# ── Chunk meta ──


def get_chunks_meta(session: Session, topic_id: str) -> dict:
    """Return lightweight chunk metadata including per-chapter breakdown."""
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
    ).all()

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    document_id = doc.id if doc else None

    from models.chapter import Chapter

    chapters = session.exec(
        select(Chapter).where(Chapter.topic_id == topic_id).order_by(Chapter.chapter_index)
    ).all()

    if not chunks:
        return {
            "topic_id": topic_id,
            "document_id": document_id,
            "chunk_count": 0,
            "chapter_count": 0,
            "total_chars": 0,
            "estimated_tokens": 0,
            "first_chunk_index": None,
            "last_chunk_index": None,
            "chunks_by_chapter": [],
        }

    total_chars = sum(c.char_count for c in chunks)
    estimated_tokens = sum(c.estimated_tokens for c in chunks)

    chunks_by_chapter = []
    for ch in chapters:
        ch_chunks = [c for c in chunks if c.chapter_index == ch.chapter_index]
        if not ch_chunks:
            continue
        chunks_by_chapter.append(
            {
                "chapter_index": ch.chapter_index,
                "title": ch.title,
                "chunk_count": len(ch_chunks),
                "char_count": sum(c.char_count for c in ch_chunks),
                "estimated_tokens": sum(c.estimated_tokens for c in ch_chunks),
            }
        )

    return {
        "topic_id": topic_id,
        "document_id": document_id,
        "chunk_count": len(chunks),
        "chapter_count": len(chapters),
        "total_chars": total_chars,
        "estimated_tokens": estimated_tokens,
        "first_chunk_index": chunks[0].chunk_index,
        "last_chunk_index": chunks[-1].chunk_index,
        "first_global_chunk_index": 0,
        "last_global_chunk_index": len(chunks) - 1 if chunks else None,
        "chunks_by_chapter": chunks_by_chapter,
    }


# ── Chunk selection ──


def select_chunks_for_analysis(
    session: Session,
    topic_id: str,
    mode: str,
    limit_chunks: int | None = None,
    range_start: int | None = None,
    range_end: int | None = None,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    incremental_run_id: str | None = None,
    safety_cap: int | None = None,
) -> tuple[list[Chunk], dict]:
    """Select chunks based on analysis mode. Returns (chunks, selection_info)."""
    validate_analysis_mode(mode)

    all_chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
    ).all()

    if not all_chunks:
        return [], {"mode": mode, "selected": 0, "reason": "no_chunks"}

    if mode == AnalysisMode.PREVIEW:
        return _select_preview(all_chunks, limit_chunks)
    elif mode == AnalysisMode.RANGE:
        return _select_range(all_chunks, range_start, range_end, chapter_start, chapter_end)
    elif mode == AnalysisMode.FULL:
        return _select_full(all_chunks, safety_cap)
    elif mode == AnalysisMode.INCREMENTAL:
        return _select_incremental(all_chunks, session, topic_id, incremental_run_id)
    else:
        raise ValueError(f"Unknown analysis mode: {mode}")


def _select_preview(chunks: list[Chunk], limit_chunks: int | None) -> tuple[list[Chunk], dict]:
    if limit_chunks is not None and limit_chunks <= 0:
        raise ValueError("limit_chunks must be > 0")
    n = limit_chunks or _recommended_preview_limit(chunks)
    selected = chunks[: min(n, len(chunks))]
    return selected, {
        "mode": "preview",
        "selected": len(selected),
        "total": len(chunks),
        "limit_chunks": n,
    }


def _select_range(
    chunks: list[Chunk],
    range_start: int | None,
    range_end: int | None,
    chapter_start: int | None,
    chapter_end: int | None,
) -> tuple[list[Chunk], dict]:
    has_chunk_range = range_start is not None or range_end is not None
    has_chapter_range = chapter_start is not None or chapter_end is not None

    if has_chunk_range and has_chapter_range:
        raise ValueError("Cannot specify both chunk range and chapter range")
    if not has_chunk_range and not has_chapter_range:
        raise ValueError("Range mode requires chunk range or chapter range")

    if has_chunk_range:
        rs = range_start or 0
        re = range_end if range_end is not None else len(chunks) - 1
        if rs < 0 or re < 0:
            raise ValueError("Range start/end must not be negative")
        if rs > re:
            raise ValueError("range_start must not be greater than range_end")
        selected = [c for i, c in enumerate(chunks) if rs <= i <= re]
    else:
        cs = chapter_start or 0
        ce = chapter_end if chapter_end is not None else max(c.chapter_index or 0 for c in chunks)
        if cs < 0 or ce < 0:
            raise ValueError("Chapter start/end must not be negative")
        if cs > ce:
            raise ValueError("chapter_start must not be greater than chapter_end")
        selected = [c for c in chunks if cs <= (c.chapter_index or 0) <= ce]

    info: dict = {
        "mode": "range",
        "selected": len(selected),
        "total": len(chunks),
        "chapter_start": chapter_start,
        "chapter_end": chapter_end,
        "range_start": range_start,
        "range_end": range_end,
    }
    if not selected:
        info["reason"] = "empty_range"
    return selected, info


def _select_full(chunks: list[Chunk], safety_cap: int | None) -> tuple[list[Chunk], dict]:
    if safety_cap is not None and safety_cap <= 0:
        raise ValueError("safety_cap must be > 0")
    if safety_cap is not None and len(chunks) > safety_cap:
        selected = chunks[:safety_cap]
        return selected, {
            "mode": "full",
            "selected": len(selected),
            "total": len(chunks),
            "capped": True,
            "safety_cap": safety_cap,
        }
    return chunks, {"mode": "full", "selected": len(chunks), "total": len(chunks)}


def _select_incremental(
    chunks: list[Chunk],
    session: Session,
    topic_id: str,
    incremental_run_id: str | None = None,
) -> tuple[list[Chunk], dict]:
    """Select chunks not yet successfully extracted.

    If incremental_run_id is provided, use that run as the base.
    Otherwise, use the latest AnalysisRun for the topic.
    Falls back to full if no previous runs exist.
    """
    from models.analysis_run import AnalysisRun
    from models.local_extraction import LocalExtraction

    base_run = None
    if incremental_run_id:
        base_run = session.get(AnalysisRun, incremental_run_id)
        if base_run is None:
            raise ValueError(f"AnalysisRun not found: {incremental_run_id}")
        if base_run.topic_id != topic_id:
            raise ValueError("AnalysisRun does not belong to this topic")

    if not base_run:
        base_run = session.exec(
            select(AnalysisRun)
            .where(AnalysisRun.topic_id == topic_id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(1)
        ).first()

    if not base_run:
        return chunks, {
            "mode": "incremental",
            "selected": len(chunks),
            "total": len(chunks),
            "fallback": "no_previous_run",
        }

    succeeded_ids: set[str] = set()
    extractions = session.exec(
        select(LocalExtraction)
        .where(LocalExtraction.run_id == base_run.id)
        .where(LocalExtraction.status == "succeeded")
    ).all()
    for ext in extractions:
        if ext.chunk_id:
            succeeded_ids.add(ext.chunk_id)

    remaining = [c for c in chunks if c.id not in succeeded_ids]
    return remaining, {
        "mode": "incremental",
        "selected": len(remaining),
        "total": len(chunks),
        "succeeded_previous": len(succeeded_ids),
        "base_run_id": base_run.id,
    }


def _recommended_preview_limit(chunks: list[Chunk]) -> int:
    total = len(chunks)
    if total <= 3:
        return max(1, total)
    if total <= 10:
        return 3
    if total <= 50:
        return 5
    return 3


def validate_analysis_mode(mode: str) -> None:
    """Raise ValueError if mode is not a valid AnalysisMode."""
    if mode not in {m.value for m in AnalysisMode}:
        raise ValueError(f"Invalid mode '{mode}'. Must be: preview, range, full, incremental")


# ── Cost estimation ──


def estimate_v2_analysis_cost(
    selected_chunks: list[Chunk],
    requested_types: list[str] | None = None,
) -> dict:
    """Estimate token cost for a v0.2 analysis run."""
    n = len(selected_chunks)
    if n == 0:
        return {
            "selected_chunk_count": 0,
            "selected_chars": 0,
            "selected_estimated_tokens": 0,
            "estimated_local_extraction_input_tokens": 0,
            "estimated_local_extraction_output_tokens": 0,
            "estimated_merge_input_tokens": 0,
            "estimated_final_input_total": 0,
            "estimated_final_output_total": 0,
            "estimated_total_input_tokens": 0,
            "estimated_total_output_tokens": 0,
            "estimate_notes": "No chunks selected.",
        }

    selected_chars = sum(c.char_count for c in selected_chunks)
    selected_tokens = sum(c.estimated_tokens for c in selected_chunks)

    types = requested_types or []
    type_count = len(types) if types else 6

    extraction_input = n * 800 + selected_tokens
    extraction_output = n * 2048

    # Merge: deterministic Python, zero LLM cost
    merge_input = 0
    merge_output = 0

    # Final synthesis: total across all types
    final_input_total = type_count * 1200
    final_output_total = type_count * 1024

    total_input = extraction_input + merge_input + final_input_total
    total_output = extraction_output + merge_output + final_output_total

    return {
        "selected_chunk_count": n,
        "selected_chars": selected_chars,
        "selected_estimated_tokens": selected_tokens,
        "estimated_local_extraction_input_tokens": extraction_input,
        "estimated_local_extraction_output_tokens": extraction_output,
        "estimated_merge_input_tokens": merge_input,
        "estimated_final_input_total": final_input_total,
        "estimated_final_output_total": final_output_total,
        "estimated_total_input_tokens": total_input,
        "estimated_total_output_tokens": total_output,
        "estimate_notes": (
            "v0.2: each chunk sent once for local_extraction. "
            "Merge stage is deterministic Python (no LLM cost). "
            "Final synthesis: one LLM call per requested type. "
            f"Default types: {type_count}. "
            "Estimates assume Chinese text (~1.5 chars/token). "
            "Actual cost depends on model and provider."
        ),
    }
