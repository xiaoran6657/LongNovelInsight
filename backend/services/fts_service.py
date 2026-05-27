"""SQLite FTS5 full-text search over chunk text and titles.

FTS5 virtual tables have no FK cascade — cleanup must be done explicitly
in document deletion, topic deletion, and re-parse paths.

BM25 scoring: FTS5 returns negative scores by default (more negative = better).
We negate them so higher score = more relevant, consistent with the keyword
fallback and the existing retrieval_service.py scoring convention.
"""

import logging
import re

from sqlalchemy import text
from sqlmodel import Session, select

from models.chapter import Chapter
from models.chunk import Chunk

logger = logging.getLogger(__name__)

FTS_TABLE = "chunk_fts"
DEFAULT_LIMIT = 20
MAX_SNIPPET_CHARS = 300

# CJK character range for detecting Chinese/Japanese/Korean text
_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")
# English word token pattern for query analysis
_WORD_RE = re.compile(r"\w{2,}")


def ensure_chunk_fts_table(session: Session) -> None:
    """Create the FTS5 virtual table if it does not already exist (idempotent)."""
    ddl = f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
      chunk_id UNINDEXED,
      topic_id UNINDEXED,
      document_id UNINDEXED,
      chapter_index UNINDEXED,
      chunk_index UNINDEXED,
      title,
      text,
      tokenize = 'unicode61'
    );
    """
    session.exec(text(ddl))
    logger.info("FTS5 table %s ensured.", FTS_TABLE)


# ── Index management ──


def rebuild_topic_chunk_fts(topic_id: str, session: Session) -> int:
    """Rebuild FTS index for all chunks in a topic.

    Deletes existing rows for the topic, then inserts one row per chunk.
    Uses a DELETE + INSERT within the same transaction for atomicity.
    Returns the number of rows inserted.
    """
    ensure_chunk_fts_table(session)
    delete_topic_chunk_fts(topic_id, session)

    chunks = session.exec(
        select(Chunk).where(Chunk.topic_id == topic_id).order_by(Chunk.chunk_index)
    ).all()

    if not chunks:
        return 0

    # Resolve chapter titles for each chunk
    chapter_map: dict[str, str] = {}
    chapter_ids = {c.chapter_id for c in chunks if c.chapter_id}
    if chapter_ids:
        chapters = session.exec(
            select(Chapter).where(Chapter.id.in_(chapter_ids))  # type: ignore[arg-type]
        ).all()
        chapter_map = {ch.id: ch.title for ch in chapters}

    rows = []
    for chunk in chunks:
        title = chapter_map.get(chunk.chapter_id, "") if chunk.chapter_id else ""
        # Escape double quotes in content for FTS5 INSERT
        safe_title = title.replace('"', '""')
        safe_text = (chunk.text or "").replace('"', '""')
        rows.append(
            f'("{chunk.id}", "{chunk.topic_id}", "{chunk.document_id}", '
            f'"{chunk.chapter_index or 0}", "{chunk.chunk_index}", '
            f'"{safe_title}", "{safe_text}")'
        )

    # Batch insert for performance
    columns = "chunk_id, topic_id, document_id, chapter_index, chunk_index, title, text"
    values = ", ".join(rows)
    session.exec(text(f"INSERT INTO {FTS_TABLE} ({columns}) VALUES {values}"))
    session.commit()
    logger.info("FTS rebuild for topic %s: %d rows.", topic_id, len(rows))
    return len(rows)


def delete_topic_chunk_fts(topic_id: str, session: Session) -> None:
    """Delete all FTS rows for a topic. Idempotent — safe to call on empty index.

    Does NOT commit — caller controls the transaction boundary.
    Safe to call when the FTS table hasn't been created yet.
    """
    ensure_chunk_fts_table(session)
    session.exec(text(f"DELETE FROM {FTS_TABLE} WHERE topic_id = :tid").bindparams(tid=topic_id))


# ── Search ──


def _is_cjk_query(query: str) -> bool:
    """Return True if the query contains CJK characters."""
    return bool(_CJK_RE.search(query))


def _fts_query_string(user_query: str) -> str:
    """Build a safe FTS5 query string from user input.

    Escapes double quotes and wraps each token for prefix/term matching.
    FTS5 with unicode61 tokenizer handles ASCII tokens well;
    CJK characters are passed through for substring matching.
    """
    # Remove characters that have special meaning in FTS5
    cleaned = user_query.replace('"', "").replace("*", "").replace("(", "").replace(")", "")
    if not cleaned.strip():
        return ""
    # Quote the query to treat it as a phrase
    return f'"{cleaned.strip()}"'


def search_chunks_fts(
    topic_id: str,
    query: str,
    session: Session,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """Search chunks via FTS5 full-text index.

    Returns list of dicts with: chunk_id, topic_id, chapter_index, chunk_index,
    title, snippet, score (higher = better, BM25 negated).
    """
    if not query or not query.strip():
        return []

    fts_query = _fts_query_string(query)
    if not fts_query:
        return []

    # bm25() returns negative values; negate so higher = better.
    # FTS5 column layout (0-indexed):
    #   0=chunk_id, 1=topic_id, 2=document_id, 3=chapter_index,
    #   4=chunk_index, 5=title, 6=text
    # snippet() column index 6 = text column.
    sql = text(
        f"SELECT c.chunk_id, c.topic_id, CAST(c.chapter_index AS INTEGER), "
        f"CAST(c.chunk_index AS INTEGER), "
        f"c.title, snippet({FTS_TABLE}, 6, '<b>', '</b>', '...', 32) AS snippet, "
        f"-rank AS score "
        f"FROM {FTS_TABLE} c "
        f"WHERE {FTS_TABLE} MATCH :query "
        f"AND c.topic_id = :topic_id "
        f"ORDER BY rank "
        f"LIMIT :limit"
    ).bindparams(query=fts_query, topic_id=topic_id, limit=limit)

    result = session.exec(sql)
    rows = result.fetchall()
    return [
        {
            "chunk_id": row[0],
            "topic_id": row[1],
            "chapter_index": row[2],
            "chunk_index": row[3],
            "title": row[4] or "",
            "snippet": _strip_fts_tags(row[5] or ""),
            "score": round(row[6], 1) if row[6] is not None else 0.0,
            "method": "fts",
        }
        for row in rows
    ]


def _strip_fts_tags(snippet: str) -> str:
    """Remove FTS5 highlight markers from a snippet."""
    return snippet.replace("<b>", "").replace("</b>", "")


def _make_excerpt(text: str, query: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
    """Return a snippet of text centered around the first match of query."""
    if len(text) <= max_chars:
        return text

    lower_text = text.lower()
    lower_query = query.strip().lower()
    pos = lower_text.find(lower_query)
    if pos == -1:
        pos = 0

    half = max_chars // 2
    start = max(0, pos - half)
    end = min(len(text), start + max_chars)
    if end < len(text):
        start = max(0, end - max_chars)

    excerpt = text[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt


def search_chunks_keyword_fallback(
    topic_id: str,
    query: str,
    session: Session,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """Fallback search using SQL LIKE for CJK or when FTS returns no results.

    Uses LIKE '%keyword%' substring matching on chunk text.
    Returns same shape as search_chunks_fts().
    """
    if not query or not query.strip():
        return []

    pattern = f"%{query.strip()}%"
    sql = text(
        "SELECT c.id, c.topic_id, c.chapter_index, c.chunk_index, "
        "CASE WHEN ch.title IS NULL THEN '' ELSE ch.title END AS title, "
        "c.text "
        "FROM chunk c "
        "LEFT JOIN chapter ch ON ch.id = c.chapter_id "
        "WHERE c.topic_id = :topic_id AND c.text LIKE :pattern "
        "LIMIT :limit"
    ).bindparams(topic_id=topic_id, pattern=pattern, limit=limit)

    result = session.exec(sql)
    rows = result.fetchall()
    return [
        {
            "chunk_id": row[0],
            "topic_id": row[1],
            "chapter_index": row[2],
            "chunk_index": row[3],
            "title": row[4] or "",
            "snippet": _make_excerpt(row[5] or "", query),
            "score": 0.0,  # LIKE has no scoring — matches are binary
            "method": "keyword_fallback",
        }
        for row in rows
    ]
