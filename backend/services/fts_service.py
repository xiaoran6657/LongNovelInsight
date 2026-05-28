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
# Common CJK grammatical function characters that are too frequent to be useful
# as single-character search terms. Filtered out during char-overlap expansion.
_CJK_STOP_CHARS: frozenset[str] = frozenset(
    {
        "的",
        "了",
        "是",
        "在",
        "我",
        "他",
        "她",
        "它",
        "们",
        "这",
        "那",
        "不",
        "也",
        "就",
        "都",
        "和",
        "与",
        "很",
        "要",
        "会",
        "能",
        "有",
        "没",
        "你",
        "吗",
        "呢",
        "吧",
        "啊",
        "哦",
        "嗯",
        "但",
        "而",
        "且",
        "或",
        "所",
        "被",
        "把",
        "从",
        "对",
        "向",
        "往",
        "朝",
        "到",
        "给",
        "为",
        "以",
        "可",
        "着",
        "过",
        "得",
        "地",
        "之",
        "其",
        "一",
        "个",
        "些",
        "每",
        "各",
        "某",
        "什",
        "么",
        "怎",
        "样",
        "谁",
        "哪",
        "几",
        "还",
        "又",
        "再",
        "才",
        "刚",
        "已",
        "将",
        "正",
        "只",
        "最",
        "更",
        "太",
        "好",
        "来",
        "去",
        "说",
        "看",
        "让",
        "用",
        "做",
        "想",
        "知",
        "道",
        "人",
        "年",
        "日",
        "月",
        "时",
        "子",
        "儿",
        "头",
        "大",
        "小",
        "多",
        "少",
        "上",
        "下",
        "里",
        "中",
        "前",
        "后",
        "出",
        "进",
        "种",
        "点",
        "处",
        "等",
        "间",
        "当",
        "成",
    }
)


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
        session.commit()
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


def _fts_safe_tokens(user_query: str) -> list[str]:
    """Extract alphanumeric tokens safe for FTS5.

    Strips all characters that have special meaning in FTS5 or could
    trigger syntax errors (?, :, -, punctuation, etc.).
    """
    # Replace non-alphanumeric/non-space characters with space
    cleaned = re.sub(r"[^\w\s]", " ", user_query)
    return [t for t in cleaned.split() if t]


def _fts_query_string(user_query: str) -> str:
    """Build a safe FTS5 query string with explicit OR between tokens.

    Each token is double-quoted so FTS5 treats it as a literal phrase term,
    never as an operator (OR, AND, NOT). OR between tokens ensures any-match
    semantics rather than FTS5's implicit AND.
    """
    tokens = _fts_safe_tokens(user_query)
    if not tokens:
        return ""
    # Quote each token individually to prevent FTS reserved-word collisions
    quoted = [f'"{t}"' for t in tokens]
    if len(quoted) == 1:
        return quoted[0]
    return " OR ".join(quoted)


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

    try:
        result = session.exec(sql)
        rows = result.fetchall()
    except Exception:
        logger.warning("FTS query failed for topic %s: %s", topic_id, query, exc_info=True)
        return []
    return [
        {
            "chunk_id": row[0],
            "topic_id": row[1],
            "chapter_index": row[2],
            "chunk_index": row[3],
            "title": row[4] or "",
            "snippet": _strip_fts_tags(row[5] or ""),
            "score": round(row[6], 2) if row[6] is not None else 0.0,
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


def search_chunks(
    topic_id: str,
    query: str,
    session: Session,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """Unified search: FTS first, keyword fallback for CJK or empty FTS results.

    Deduplicates by chunk_id so the same chunk doesn't appear twice when
    both FTS and fallback match it.
    """
    if not query or not query.strip():
        return []

    # FTS search first
    results = search_chunks_fts(topic_id, query, session, limit)

    # Fall back to keyword search for CJK queries or empty FTS results
    if _is_cjk_query(query) or len(results) == 0:
        fallback = search_chunks_keyword_fallback(topic_id, query, session, limit)
        seen = {r["chunk_id"] for r in results}
        for r in fallback:
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                results.append(r)

    # Sort by score descending, then limit
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def search_chunks_keyword_fallback(
    topic_id: str,
    query: str,
    session: Session,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """Fallback search using SQL LIKE for CJK or when FTS returns no results.

    Strips punctuation from the query (same as FTS path), then constructs
    LIKE '%token%' conditions joined with OR for multi-token queries.
    CJK tokens also get an AND group of deduplicated non-stop characters
    to catch unsegmented overlap (e.g. "刘备曹操" also matches "刘备和曹操").
    Returns same shape as search_chunks_fts().
    """
    if not query or not query.strip():
        return []

    tokens = _fts_safe_tokens(query)
    if not tokens:
        return []

    # Escape LIKE wildcards in all tokens
    def _escape_like(s: str) -> str:
        return s.replace("%", "\\%").replace("_", "\\_")

    # Build OR groups: each group is a list of LIKE conditions that are
    # AND'd together; groups are OR'd. Full tokens become single-condition
    # groups. CJK tokens with 2+ non-stop chars also get an AND group
    # requiring all those characters to appear (char-overlap matching).
    seen: set[str] = set()
    or_groups: list[list[str]] = []
    params: dict = {"topic_id": topic_id, "limit": limit}
    param_idx = 0

    for t in tokens:
        escaped = _escape_like(t)
        if escaped not in seen:
            seen.add(escaped)
            or_groups.append([f"c.text LIKE :p{param_idx} ESCAPE '\\'"])
            params[f"p{param_idx}"] = f"%{escaped}%"
            param_idx += 1

        # For all-CJK tokens > 1 char, build char-overlap AND group
        # using only non-stop characters to avoid false matches from
        # common function characters (的, 了, 是, 在, etc.)
        if len(t) > 1 and all(_CJK_RE.match(ch) for ch in t):
            non_stop = list(dict.fromkeys(ch for ch in t if ch not in _CJK_STOP_CHARS))
            if len(non_stop) >= 2:
                and_conds: list[str] = []
                for ch in non_stop:
                    and_conds.append(f"c.text LIKE :p{param_idx} ESCAPE '\\'")
                    params[f"p{param_idx}"] = f"%{_escape_like(ch)}%"
                    param_idx += 1
                or_groups.append(and_conds)

    if not or_groups:
        return []

    or_clauses: list[str] = []
    for group in or_groups:
        if len(group) == 1:
            or_clauses.append(group[0])
        else:
            or_clauses.append("(" + " AND ".join(group) + ")")

    where = " OR ".join(or_clauses)
    sql = text(
        "SELECT c.id, c.topic_id, c.chapter_index, c.chunk_index, "
        "CASE WHEN ch.title IS NULL THEN '' ELSE ch.title END AS title, "
        "c.text "
        "FROM chunk c "
        "LEFT JOIN chapter ch ON ch.id = c.chapter_id "
        f"WHERE c.topic_id = :topic_id AND ({where}) "
        "LIMIT :limit"
    ).bindparams(**params)

    # Build a display query from the cleaned tokens for snippet extraction
    display_query = " ".join(tokens)

    result = session.exec(sql)
    rows = result.fetchall()
    return [
        {
            "chunk_id": row[0],
            "topic_id": row[1],
            "chapter_index": row[2],
            "chunk_index": row[3],
            "title": row[4] or "",
            "snippet": _make_excerpt(row[5] or "", display_query),
            "score": 0.0,
            "method": "keyword_fallback",
        }
        for row in rows
    ]
