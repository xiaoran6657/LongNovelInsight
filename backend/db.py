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


def _migrate_local_extraction_usage_columns() -> None:
    """Add cumulative usage and attempt tracking columns to local_extraction if missing."""
    columns = [
        ("reasoning_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("prompt_cache_hit_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("prompt_cache_miss_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("usage_unavailable_attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("attempt_usage_json", "TEXT"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE local_extraction ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass
        conn.commit()


def _migrate_v04_work_tables(_engine=None) -> None:
    """v0.4 multi-Work schema: work table, document rebuild, cross-work tables.

    Idempotent — safe to run multiple times. Skips if ix_document_work_id exists.
    Accepts optional _engine for testing; defaults to module-level engine.
    """
    from sqlalchemy import inspect as sa_inspect

    eng = _engine or engine

    # Guard: skip if already migrated
    insp = sa_inspect(eng)
    indexes = {i["name"] for i in insp.get_indexes("document")}
    if "ix_document_work_id" in indexes:
        return

    # 1. Create work table FIRST (document rebuild references work.id FK)
    from models.work import Work

    SQLModel.metadata.create_all(eng, tables=[Work.__table__])  # type: ignore[arg-type]
    # 2. Document table rebuild via raw sqlite3 connection
    # SQLAlchemy transactions conflict with PRAGMA foreign_keys; use raw connection
    # Wrap in a context manager to ensure the connection returns to the pool
    with eng.connect() as conn:
        raw = conn.connection.dbapi_connection
        raw.execute("PRAGMA foreign_keys = OFF")
        raw.execute("DROP TABLE IF EXISTS document_new")
        raw.execute(
            """CREATE TABLE document_new (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL REFERENCES topic(id),
            work_id TEXT REFERENCES work(id),
            original_filename TEXT NOT NULL DEFAULT '',
            stored_filename TEXT NOT NULL DEFAULT 'original.txt',
            file_type TEXT NOT NULL DEFAULT 'txt',
            content_type TEXT,
            encoding TEXT NOT NULL DEFAULT 'utf-8',
            file_size_bytes INTEGER NOT NULL DEFAULT 0,
            char_count INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL DEFAULT '',
            metadata_json TEXT,
            status TEXT NOT NULL DEFAULT 'uploaded',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
        )
        raw.execute(
            """INSERT INTO document_new (
            id, topic_id, work_id, original_filename, stored_filename,
            file_type, content_type, encoding, file_size_bytes, char_count,
            storage_path, metadata_json, status, created_at, updated_at
        ) SELECT
            id, topic_id, NULL, original_filename, stored_filename,
            file_type, content_type, encoding, file_size_bytes, char_count,
            storage_path, metadata_json, status, created_at, updated_at
        FROM document"""
        )
        raw.execute("DROP TABLE document")
        raw.execute("ALTER TABLE document_new RENAME TO document")
        raw.execute("PRAGMA foreign_keys = ON")

    # 3. Create remaining new tables via SQLModel
    from models.cross_work_run import CrossWorkRun
    from models.entity_mention import EntityMention
    from models.global_entity import GlobalEntity
    from models.graph_snapshot import GraphSnapshot
    from models.timeline_item import TimelineItem

    SQLModel.metadata.create_all(
        eng,
        tables=[
            GlobalEntity.__table__,  # type: ignore[arg-type]
            EntityMention.__table__,  # type: ignore[arg-type]
            CrossWorkRun.__table__,  # type: ignore[arg-type]
            GraphSnapshot.__table__,  # type: ignore[arg-type]
            TimelineItem.__table__,  # type: ignore[arg-type]
        ],
    )

    # 4. Partial unique index on document(work_id)
    with eng.connect() as conn:
        conn.connection.dbapi_connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_document_work_id "
            "ON document(work_id) WHERE work_id IS NOT NULL"
        )

    # 5. Data migration: create default Works for legacy Topics with Documents
    from sqlmodel import Session, select

    from models.document import Document
    from models.topic import Topic

    with Session(eng) as session:
        topics_with_doc = session.exec(
            select(Topic).where(
                Topic.id.in_(
                    select(Document.topic_id).where(Document.work_id.is_(None))  # type: ignore[arg-type]
                )
            )
        ).all()

        migrated = 0
        for topic in topics_with_doc:
            doc = session.exec(
                select(Document).where(Document.topic_id == topic.id)
            ).first()
            if doc is None or doc.work_id is not None:
                continue

            existing_work = session.exec(
                select(Work).where(Work.topic_id == topic.id).order_by(Work.series_index)
            ).first()
            if existing_work is not None:
                work = existing_work
            else:
                title = doc.original_filename
                if title.endswith(".txt") or title.endswith(".epub"):
                    title = title.rsplit(".", 1)[0]
                work = Work(
                    topic_id=topic.id,
                    title=title,
                    series_index=1,
                    status=doc.status if doc.status != "uploaded" else "uploaded",
                )
                session.add(work)
                session.flush()

            doc.work_id = work.id
            session.add(doc)
            migrated += 1

        if migrated > 0:
            logger.info("v0.4 migration: created default Works for %d Topics", migrated)
        session.commit()


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
    _migrate_local_extraction_usage_columns()
    _migrate_v04_work_tables()
