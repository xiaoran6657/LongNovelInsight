"""SQLite FTS5 full-text search over chunk text and titles.

FTS5 virtual tables have no FK cascade — cleanup must be done explicitly
in document deletion, topic deletion, and re-parse paths.
"""

import logging

from sqlalchemy import text
from sqlmodel import Session

logger = logging.getLogger(__name__)

FTS_TABLE = "chunk_fts"


def ensure_chunk_fts_table(session: Session) -> None:
    """Create the FTS5 virtual table if it does not already exist (idempotent).

    Columns:
      - chunk_id, topic_id, document_id, chapter_index, chunk_index: UNINDEXED
      - title, text: indexed content columns
    """
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
    session.commit()
    logger.info("FTS5 table %s ensured.", FTS_TABLE)
