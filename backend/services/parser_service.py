"""v0.3 Unified parse pipeline — TXT and EPUB share the same Chapter/Chunk creation.

parse_novel() routes by Document.file_type, calls the appropriate adapter
to build a SourceDocument, then feeds it into the shared _persist_parse()
for DB writes with source locator fields.
"""

import json
import logging
import math
import re

from sqlmodel import Session, delete, select

from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.topic import Topic
from services import storage
from services.source_document import SourceChapter, SourceDocument

logger = logging.getLogger(__name__)

TARGET_CHUNK_CHARS = 4000
MIN_CHUNK_CHARS = 3000
MAX_CHUNK_CHARS = 5000
OVERLAP_CHARS = 300

CHAPTER_PATTERN = re.compile(
    r"^\s*(第[一二三四五六七八九十百千万\d]+[章节回]|Chapter\s+\d+|CHAPTER\s+\d+)"
)


# ── TXT adapter ──


def _txt_to_source_document(topic_id: str, doc: Document) -> SourceDocument:
    """Read a TXT file from disk and build a SourceDocument."""
    source_path = storage.get_original_txt_path(topic_id)
    if not source_path.exists():
        raise ValueError("Original text file not found on disk")

    text = source_path.read_text(encoding="utf-8")
    detected = _detect_chapters(text)
    total_chars = len(text)

    raw_chapters: list[dict] = []
    for i, d in enumerate(detected):
        start = d["start_char"]
        end = detected[i + 1]["start_char"] if i + 1 < len(detected) else total_chars
        raw_chapters.append({"title": d["title"], "start_char": start, "end_char": end, "index": i})

    chapters = []
    for ch_info in raw_chapters:
        ch_text = text[ch_info["start_char"] : ch_info["end_char"]]
        chapters.append(
            SourceChapter(
                title=ch_info["title"],
                text=ch_text,
                chapter_index=ch_info["index"],
                source_href="txt://original",
                nav_order=ch_info["index"],
            )
        )

    return SourceDocument(
        document_id=doc.id,
        topic_id=topic_id,
        file_type="txt",
        original_filename=doc.original_filename,
        storage_path=doc.storage_path,
        metadata={
            "source_format": "txt",
            "encoding": doc.encoding,
            "total_chars": total_chars,
        },
        chapters=chapters,
    )


# ── EPUB adapter ──


def _epub_to_source_document(topic_id: str, doc: Document) -> SourceDocument:
    """Parse an EPUB file from disk using the EPUB parser service."""
    from services.epub_parser_service import parse_epub

    source_path = storage.get_source_file_path(topic_id, doc.stored_filename)
    return parse_epub(source_path, topic_id, doc.id, doc.original_filename)


# ── Shared parse persistence ──


def _normalize_text(text: str) -> str:
    """Collapse excessive blank lines and trim per-line trailing whitespace."""
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def _estimate_tokens(char_count: int) -> int:
    return max(1, math.ceil(char_count / 1.5))


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


def _persist_parse(topic_id: str, doc: Document, source: SourceDocument, session: Session) -> dict:
    """Write Chapter/Chunk rows from a SourceDocument, with locator fields.

    Idempotent: removes old chapters/chunks before writing new ones.
    Updates Document.char_count, .status, .metadata_json, and Topic.storage_bytes.
    """
    # Idempotent: remove old chapters and chunks
    session.exec(delete(Chunk).where(Chunk.topic_id == topic_id))  # type: ignore[arg-type]
    session.exec(delete(Chapter).where(Chapter.topic_id == topic_id))  # type: ignore[arg-type]
    session.flush()

    total_chars = 0
    chapter_models: list[Chapter] = []
    all_chunks: list[Chunk] = []

    for ch in source.chapters:
        ch_text = ch.text
        ch_char_count = len(ch_text)

        chapter = Chapter(
            topic_id=topic_id,
            document_id=doc.id,
            chapter_index=ch.chapter_index,
            title=ch.title,
            start_char=0,  # per-chapter offsets reset; global offsets in chunk locators
            end_char=ch_char_count,
            char_count=ch_char_count,
            source_href=ch.source_href,
            nav_order=ch.nav_order if ch.nav_order is not None else ch.chapter_index,
            metadata_json=(json.dumps(ch.metadata, ensure_ascii=False) if ch.metadata else None),
        )
        session.add(chapter)
        session.flush()
        chapter_models.append(chapter)

        # Split chapter text into overlapping chunks
        chunk_spans = _split_into_chunks(ch_text, 0, ch_char_count)
        for ci, (cs, ce) in enumerate(chunk_spans):
            chunk_text = _normalize_text(ch_text[cs:ce])
            locator = {
                "source_type": source.file_type,
                "href": ch.source_href,
                "chapter_index": ch.chapter_index,
                "chapter_title": ch.title,
                "chunk_index": ci,
                "start_char": cs,
                "end_char": ce,
            }
            chunk = Chunk(
                topic_id=topic_id,
                document_id=doc.id,
                chapter_id=chapter.id,
                chunk_index=ci,
                chapter_index=ch.chapter_index,
                text=chunk_text,
                start_char=cs,
                end_char=ce,
                char_count=ce - cs,
                estimated_tokens=_estimate_tokens(ce - cs),
                source_locator_json=json.dumps(locator, ensure_ascii=False),
            )
            session.add(chunk)
            all_chunks.append(chunk)
            total_chars += ch_char_count

    # Update document
    doc.char_count = total_chars
    doc.status = "parsed"
    if not doc.metadata_json:
        doc.metadata_json = json.dumps(source.metadata, ensure_ascii=False)
    else:
        # Merge with existing metadata (preserves upload-time fields)
        try:
            existing = json.loads(doc.metadata_json)
        except (json.JSONDecodeError, TypeError):
            existing = {}
        existing.update(source.metadata)
        doc.metadata_json = json.dumps(existing, ensure_ascii=False)
    session.add(doc)

    # Update topic
    topic = session.get(Topic, topic_id)
    if topic is not None:
        topic.storage_bytes = doc.file_size_bytes
        session.add(topic)

    session.commit()

    total_estimated_tokens = sum(c.estimated_tokens for c in all_chunks)
    warnings = source.metadata.get("parsing_warnings", [])
    result: dict = {
        "chapter_count": len(chapter_models),
        "chunk_count": len(all_chunks),
        "char_count": total_chars,
        "estimated_tokens": total_estimated_tokens,
    }
    if warnings:
        result["warnings"] = warnings
    return result


# ── Main entry point ──


def parse_novel(topic_id: str, session: Session, force: bool = False) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise ValueError("Topic not found")

    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc is None:
        raise ValueError("No document uploaded")

    available_types = {"txt", "epub"}
    if doc.file_type not in available_types:
        raise ValueError(f"Unsupported file type: {doc.file_type}")

    # Check if source file exists
    source_path = storage.get_source_file_path(topic_id, doc.stored_filename)
    if not source_path.exists():
        raise ValueError(f"Source file not found on disk: {doc.stored_filename}")

    # Check if already parsed
    existing_chunk = session.exec(select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).first()
    has_outputs = (
        session.exec(
            select(Chunk).where(Chunk.topic_id == topic_id).limit(1)  # dummy, just check outputs
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

    # Build SourceDocument from the correct adapter
    if doc.file_type == "txt":
        source = _txt_to_source_document(topic_id, doc)
    else:
        source = _epub_to_source_document(topic_id, doc)

    result = _persist_parse(topic_id, doc, source, session)

    # Warn if re-parse orphans existing analysis outputs
    if force and has_outputs:
        from models.analysis_output import AnalysisOutput

        has_analysis = (
            session.exec(
                select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id).limit(1)
            ).first()
            is not None
        )
        if has_analysis:
            result["warning"] = (
                "Re-parse completed. Existing analysis outputs reference old chunk IDs "
                "and should be re-run to stay consistent with the new parse."
            )

    return result


# ── Chapter detection (TXT adapter helper) ──


def _detect_chapters(text: str) -> list[dict]:
    positions: list[dict] = []
    offset = 0

    for line in text.split("\n"):
        stripped = line.strip()
        if len(stripped) <= 80 and CHAPTER_PATTERN.match(stripped):
            positions.append({"title": stripped, "start_char": offset})

        offset += len(line) + 1

    if not positions:
        return [{"title": "Full Text", "start_char": 0}]

    return positions
