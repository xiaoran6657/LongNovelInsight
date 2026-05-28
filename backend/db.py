import logging
from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import models  # noqa: F401 — ensure all table models register with SQLModel.metadata
from config import DB_PATH

logger = logging.getLogger(__name__)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _migrate_chat_message_usage_columns() -> None:
    """Add token usage columns to chat_message if they don't exist yet."""
    columns = [
        ("prompt_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("completion_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("total_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("model_used", "TEXT"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE chat_message ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass  # column already exists
        conn.commit()


def _migrate_analysis_output_run_id() -> None:
    """Add run_id column to analysis_output if it doesn't exist yet."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE analysis_output ADD COLUMN run_id TEXT"))
        except Exception:
            pass
        conn.commit()


def _migrate_analysis_run_final_columns() -> None:
    """Add final_total/final_succeeded/final_failed to analysis_run if missing."""
    columns = [
        ("final_total", "INTEGER NOT NULL DEFAULT 0"),
        ("final_succeeded", "INTEGER NOT NULL DEFAULT 0"),
        ("final_failed", "INTEGER NOT NULL DEFAULT 0"),
        ("final_skipped", "INTEGER NOT NULL DEFAULT 0"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE analysis_run ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass
        conn.commit()


def _migrate_analysis_artifact() -> None:
    """Create analysis_artifact table if it doesn't exist."""
    from models.analysis_artifact import AnalysisArtifact

    SQLModel.metadata.create_all(
        engine,
        tables=[AnalysisArtifact.__table__],  # type: ignore[arg-type]
    )


def _migrate_v03_source_locator_columns() -> None:
    """Add v0.3 source locator and metadata columns (nullable)."""
    migrations = [
        ("document", "metadata_json", "TEXT"),
        ("chapter", "source_href", "TEXT"),
        ("chapter", "nav_order", "INTEGER"),
        ("chapter", "metadata_json", "TEXT"),
        ("chunk", "source_locator_json", "TEXT"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
            except Exception:
                pass  # column already exists
        conn.commit()


def _migrate_retrieval_trace() -> None:
    """Create retrieval_trace table if it doesn't exist."""
    from models.retrieval_trace import RetrievalTrace

    SQLModel.metadata.create_all(
        engine,
        tables=[RetrievalTrace.__table__],  # type: ignore[arg-type]
    )


def _migrate_chunk_fts() -> None:
    """Ensure the FTS5 virtual table exists (idempotent)."""
    from services.fts_service import ensure_chunk_fts_table

    with Session(engine) as session:
        ensure_chunk_fts_table(session)


def _migrate_embedding_cache() -> None:
    """Create embedding_cache table if it doesn't exist."""
    from models.embedding_cache import EmbeddingCache

    SQLModel.metadata.create_all(
        engine,
        tables=[EmbeddingCache.__table__],  # type: ignore[arg-type]
    )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_chat_message_usage_columns()
    _migrate_analysis_output_run_id()
    _migrate_analysis_run_final_columns()
    _migrate_analysis_artifact()
    _migrate_v03_source_locator_columns()
    _migrate_retrieval_trace()
    _migrate_chunk_fts()
    _migrate_embedding_cache()
