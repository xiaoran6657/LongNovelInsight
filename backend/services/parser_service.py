import math
import re

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.topic import Topic
from services import storage

TARGET_CHUNK_CHARS = 4000
MIN_CHUNK_CHARS = 3000
MAX_CHUNK_CHARS = 5000
OVERLAP_CHARS = 300

CHAPTER_PATTERN = re.compile(
    r"^\s*(第[一二三四五六七八九十百千万\d]+[章节回]|Chapter\s+\d+|CHAPTER\s+\d+)"
)


def _detect_chapters(text: str) -> list[dict]:
    positions: list[dict] = []
    offset = 0

    for line in text.split("\n"):
        stripped = line.strip()
        if len(stripped) <= 80 and CHAPTER_PATTERN.match(stripped):
            positions.append({"title": stripped, "start_char": offset})

        offset += len(line) + 1  # +1 for newline

    if not positions:
        return [{"title": "Full Text", "start_char": 0}]

    return positions


def _estimate_tokens(char_count: int) -> int:
    return max(1, math.ceil(char_count / 1.5))


def _normalize_text(text: str) -> str:
    """Collapse excessive blank lines and trim per-line trailing whitespace."""
    import re

    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)  # strip trailing spaces
    text = re.sub(r"\n{3,}", "\n\n", text)  # max 1 blank line between paragraphs
    return text.strip("\n")


def _split_into_chunks(text: str, chapter_start: int, chapter_end: int) -> list[tuple[int, int]]:
    length = chapter_end - chapter_start
    if length <= MAX_CHUNK_CHARS:
        return [(chapter_start, chapter_end)]

    chunks: list[tuple[int, int]] = []
    pos = chapter_start
    while pos < chapter_end:
        chunk_end = min(pos + TARGET_CHUNK_CHARS, chapter_end)
        chunks.append((pos, chunk_end))
        if chunk_end >= chapter_end:
            break
        pos = chunk_end - OVERLAP_CHARS
        if pos <= (chunks[-1][0] if chunks else chapter_start):
            pos = chunk_end

    return chunks


def _get_doc_by_topic(topic_id: str, session: Session) -> Document | None:
    return session.exec(select(Document).where(Document.topic_id == topic_id)).first()


def parse_novel(topic_id: str, session: Session, force: bool = False) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    doc = _get_doc_by_topic(topic_id, session)
    if doc is None:
        raise ValueError("No document uploaded")

    txt_path = storage.get_original_txt_path(topic_id)
    if not txt_path.exists():
        raise ValueError("Original text file not found")

    # Check if already parsed
    existing_chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    has_outputs = (
        session.exec(
            select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id).limit(1)
        ).first()
        is not None
    )

    if existing_chunk and not force:
        chapters = session.exec(select(Chapter).where(Chapter.topic_id == topic_id)).all()
        chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
        return {
            "already_parsed": True,
            "chapter_count": len(chapters),
            "chunk_count": len(chunks),
            "char_count": sum(c.char_count for c in chunks),
            "estimated_tokens": sum(c.estimated_tokens for c in chunks),
            "has_outputs": has_outputs,
        }

    text = txt_path.read_text(encoding="utf-8")

    # Idempotent: remove old chapters and chunks
    from sqlmodel import delete

    session.exec(delete(Chunk).where(Chunk.topic_id == topic_id))  # type: ignore[arg-type]
    session.exec(delete(Chapter).where(Chapter.topic_id == topic_id))  # type: ignore[arg-type]
    session.flush()

    detected = _detect_chapters(text)
    total_chars = len(text)

    # Build chapters with end_char
    raw_chapters: list[dict] = []
    for i, d in enumerate(detected):
        start = d["start_char"]
        end = detected[i + 1]["start_char"] if i + 1 < len(detected) else total_chars
        raw_chapters.append({"title": d["title"], "start_char": start, "end_char": end, "index": i})

    all_chunks: list[Chunk] = []
    chapter_models: list[Chapter] = []

    for ch_info in raw_chapters:
        ch_start = ch_info["start_char"]
        ch_end = ch_info["end_char"]
        ch_char_count = ch_end - ch_start

        chapter = Chapter(
            topic_id=topic_id,
            document_id=doc.id,
            chapter_index=ch_info["index"],
            title=ch_info["title"],
            start_char=ch_start,
            end_char=ch_end,
            char_count=ch_char_count,
        )
        session.add(chapter)
        session.flush()
        chapter_models.append(chapter)

        chunk_spans = _split_into_chunks(text, ch_start, ch_end)
        for ci, (cs, ce) in enumerate(chunk_spans):
            chunk_text = _normalize_text(text[cs:ce])
            chunk = Chunk(
                topic_id=topic_id,
                document_id=doc.id,
                chapter_id=chapter.id,
                chunk_index=ci,
                chapter_index=ch_info["index"],
                text=chunk_text,
                start_char=cs,
                end_char=ce,
                char_count=ce - cs,
                estimated_tokens=_estimate_tokens(ce - cs),
            )
            session.add(chunk)
            all_chunks.append(chunk)

    # Update document and topic
    doc.char_count = total_chars
    doc.status = "parsed"
    session.add(doc)

    topic.storage_bytes = doc.file_size_bytes
    session.add(topic)

    session.commit()

    total_estimated_tokens = sum(c.estimated_tokens for c in all_chunks)

    result: dict = {
        "chapter_count": len(chapter_models),
        "chunk_count": len(all_chunks),
        "char_count": total_chars,
        "estimated_tokens": total_estimated_tokens,
    }
    if force and has_outputs:
        result["warning"] = (
            "Re-parse completed. Existing analysis outputs reference old chunk IDs "
            "and should be re-run to stay consistent with the new parse."
        )
    return result
