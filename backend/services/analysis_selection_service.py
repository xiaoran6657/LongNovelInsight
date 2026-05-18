"""Chunk selection for v0.2 analysis modes and cost estimation.

Pure Python service — no LLM calls, no DB writes.
"""

from sqlmodel import Session, select

from models.chunk import Chunk
from models.enums import AnalysisMode

# ── Chunk meta ──


def get_chunks_meta(session: Session, topic_id: str) -> dict:
    """Return lightweight chunk metadata including per-chapter breakdown."""
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.topic_id == topic_id)
        .order_by(Chunk.chapter_index, Chunk.chunk_index)
    ).all()
    if not chunks:
        return {
            "topic_id": topic_id,
            "chunk_count": 0,
            "chapter_count": 0,
            "total_chars": 0,
            "estimated_tokens": 0,
            "first_chunk_index": 0,
            "last_chunk_index": 0,
            "chunks_by_chapter": [],
        }

    from models.chapter import Chapter

    chapters = session.exec(
        select(Chapter)
        .where(Chapter.topic_id == topic_id)
        .order_by(Chapter.chapter_index)
    ).all()

    total_chars = sum(c.char_count for c in chunks)
    estimated_tokens = sum(c.estimated_tokens for c in chunks)

    chunks_by_chapter = []
    for ch in chapters:
        ch_chunks = [c for c in chunks if c.chapter_index == ch.chapter_index]
        if not ch_chunks:
            continue
        chunks_by_chapter.append({
            "chapter_index": ch.chapter_index,
            "title": ch.title,
            "chunk_count": len(ch_chunks),
            "char_count": sum(c.char_count for c in ch_chunks),
            "estimated_tokens": sum(c.estimated_tokens for c in ch_chunks),
        })

    return {
        "topic_id": topic_id,
        "chunk_count": len(chunks),
        "chapter_count": len(chapters),
        "total_chars": total_chars,
        "estimated_tokens": estimated_tokens,
        "first_chunk_index": chunks[0].chunk_index if chunks else 0,
        "last_chunk_index": chunks[-1].chunk_index if chunks else 0,
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
) -> tuple[list[Chunk], dict]:
    """Select chunks based on analysis mode. Returns (chunks, selection_info)."""
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
        return _select_full(all_chunks)
    elif mode == AnalysisMode.INCREMENTAL:
        return _select_incremental(all_chunks, session, topic_id)
    else:
        raise ValueError(f"Unknown analysis mode: {mode}")


def _select_preview(
    chunks: list[Chunk], limit_chunks: int | None
) -> tuple[list[Chunk], dict]:
    n = limit_chunks or _recommended_preview_limit(chunks)
    selected = chunks[:n]
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
    if chapter_start is not None or chapter_end is not None:
        cs = chapter_start or 0
        ce = chapter_end if chapter_end is not None else max(c.chapter_index for c in chunks)
        selected = [c for c in chunks if cs <= (c.chapter_index or 0) <= ce]
    elif range_start is not None or range_end is not None:
        rs = range_start or 0
        re = range_end if range_end is not None else max(c.chunk_index for c in chunks)
        selected = [c for c in chunks if rs <= c.chunk_index <= re]
    else:
        selected = chunks[:3]
    return selected, {
        "mode": "range",
        "selected": len(selected),
        "total": len(chunks),
        "chapter_start": chapter_start,
        "chapter_end": chapter_end,
        "range_start": range_start,
        "range_end": range_end,
    }


def _select_full(chunks: list[Chunk]) -> tuple[list[Chunk], dict]:
    return chunks, {"mode": "full", "selected": len(chunks), "total": len(chunks)}


def _select_incremental(
    chunks: list[Chunk], session: Session, topic_id: str
) -> tuple[list[Chunk], dict]:
    """Select chunks not yet successfully extracted in any previous run.

    Falls back to full if no previous runs exist.
    """
    from models.analysis_run import AnalysisRun
    from models.local_extraction import LocalExtraction

    previous_runs = session.exec(
        select(AnalysisRun)
        .where(AnalysisRun.topic_id == topic_id)
        .order_by(AnalysisRun.created_at.desc())
    ).all()

    if not previous_runs:
        return chunks, {
            "mode": "incremental",
            "selected": len(chunks),
            "total": len(chunks),
            "fallback": "no_previous_run",
        }

    # Collect all succeeded chunk IDs from any previous run
    succeeded_ids: set[str] = set()
    for run in previous_runs:
        extractions = session.exec(
            select(LocalExtraction)
            .where(LocalExtraction.run_id == run.id)
            .where(LocalExtraction.status == "succeeded")
        ).all()
        for ext in extractions:
            succeeded_ids.add(ext.chunk_id)

    remaining = [c for c in chunks if c.id not in succeeded_ids]
    return remaining, {
        "mode": "incremental",
        "selected": len(remaining),
        "total": len(chunks),
        "succeeded_previous": len(succeeded_ids),
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
    """Estimate token cost for a v0.2 analysis run.

    v0.2 sends each chunk text once (local_extraction), then merges
    without re-sending chunks. The merge stage uses deterministic
    deduplication (no LLM cost).
    """
    n = len(selected_chunks)
    if n == 0:
        return {
            "selected_chunk_count": 0,
            "selected_chars": 0,
            "selected_estimated_tokens": 0,
            "estimated_local_extraction_input_tokens": 0,
            "estimated_local_extraction_output_tokens": 0,
            "estimated_merge_input_tokens": 0,
            "estimated_final_input_tokens": 0,
            "estimated_final_output_tokens": 0,
            "estimated_total_input_tokens": 0,
            "estimated_total_output_tokens": 0,
            "estimate_notes": "No chunks selected.",
        }

    selected_chars = sum(c.char_count for c in selected_chunks)
    selected_tokens = sum(c.estimated_tokens for c in selected_chunks)

    types = requested_types or []
    type_count = len(types) if types else 6

    # Local extraction: each chunk sent once
    # ~500 tokens system prompt per chunk, plus chunk text
    prompt_per_extraction = 800  # shared rules + local_extraction prompt
    extraction_input = n * prompt_per_extraction + selected_tokens
    extraction_output = n * 2048  # estimated output per chunk

    # Merge: deterministic (Python), zero LLM cost
    merge_input = 0
    merge_output = 0

    # Final synthesis: one LLM call per type (estimated from merged atoms)
    final_input_per_type = type_count * 1200
    final_output_per_type = type_count * 1024

    total_input = extraction_input + merge_input + final_input_per_type
    total_output = extraction_output + merge_output + final_output_per_type

    return {
        "selected_chunk_count": n,
        "selected_chars": selected_chars,
        "selected_estimated_tokens": selected_tokens,
        "estimated_local_extraction_input_tokens": extraction_input,
        "estimated_local_extraction_output_tokens": extraction_output,
        "estimated_merge_input_tokens": merge_input,
        "estimated_final_input_tokens": final_input_per_type,
        "estimated_final_output_tokens": final_output_per_type,
        "estimated_total_input_tokens": total_input,
        "estimated_total_output_tokens": total_output,
        "estimate_notes": (
            "v0.2: each chunk sent once for local_extraction. "
            "Merge stage is deterministic Python (no LLM cost). "
            "Final synthesis: one LLM call per requested type. "
            "Estimates assume Chinese text (~1.5 chars/token). "
            "Actual cost depends on model and provider."
        ),
    }
