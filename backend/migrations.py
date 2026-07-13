"""Ordered, idempotent SQLite migrations for local database upgrades."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

logger = logging.getLogger(__name__)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def configure_sqlite_engine(engine: Engine) -> None:
    """Enable foreign-key enforcement for current and future pooled connections."""
    if not event.contains(engine, "connect", _enable_sqlite_foreign_keys):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")


@dataclass(frozen=True)
class Migration:
    id: str
    description: str
    apply: Callable[[Engine], None]


def add_missing_columns(engine: Engine, table: str, columns: Sequence[tuple[str, str]]) -> None:
    """Add absent columns without masking inspection or ALTER failures."""
    existing = {column["name"] for column in sa_inspect(engine).get_columns(table)}
    missing = [(name, definition) for name, definition in columns if name not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for name, definition in missing:
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}'))


def migrate_chat_message_usage_columns(engine: Engine) -> None:
    add_missing_columns(
        engine,
        "chat_message",
        [
            ("prompt_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("completion_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("total_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("model_used", "TEXT"),
        ],
    )


def migrate_analysis_output_run_id(engine: Engine) -> None:
    add_missing_columns(engine, "analysis_output", [("run_id", "TEXT")])


def migrate_analysis_run_final_columns(engine: Engine) -> None:
    add_missing_columns(
        engine,
        "analysis_run",
        [
            ("final_total", "INTEGER NOT NULL DEFAULT 0"),
            ("final_succeeded", "INTEGER NOT NULL DEFAULT 0"),
            ("final_failed", "INTEGER NOT NULL DEFAULT 0"),
            ("final_skipped", "INTEGER NOT NULL DEFAULT 0"),
        ],
    )


def migrate_analysis_artifact(engine: Engine) -> None:
    from models.analysis_artifact import AnalysisArtifact

    SQLModel.metadata.create_all(engine, tables=[AnalysisArtifact.__table__])  # type: ignore[arg-type]


def migrate_v03_source_locator_columns(engine: Engine) -> None:
    by_table: dict[str, list[tuple[str, str]]] = {}
    for table, column, definition in [
        ("document", "metadata_json", "TEXT"),
        ("chapter", "source_href", "TEXT"),
        ("chapter", "nav_order", "INTEGER"),
        ("chapter", "metadata_json", "TEXT"),
        ("chunk", "source_locator_json", "TEXT"),
    ]:
        by_table.setdefault(table, []).append((column, definition))
    for table, columns in by_table.items():
        add_missing_columns(engine, table, columns)


def migrate_retrieval_trace(engine: Engine) -> None:
    from models.retrieval_trace import RetrievalTrace

    SQLModel.metadata.create_all(engine, tables=[RetrievalTrace.__table__])  # type: ignore[arg-type]


def migrate_chunk_fts(engine: Engine) -> None:
    from services.fts_service import ensure_chunk_fts_table

    with Session(engine) as session:
        ensure_chunk_fts_table(session)


def migrate_embedding_cache(engine: Engine) -> None:
    from models.embedding_cache import EmbeddingCache

    SQLModel.metadata.create_all(engine, tables=[EmbeddingCache.__table__])  # type: ignore[arg-type]


def migrate_local_extraction_usage_columns(engine: Engine) -> None:
    add_missing_columns(
        engine,
        "local_extraction",
        [
            ("reasoning_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("prompt_cache_hit_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("prompt_cache_miss_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("usage_unavailable_attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("attempt_usage_json", "TEXT"),
        ],
    )


def migrate_v04_work_tables(engine: Engine) -> None:
    """Rebuild legacy Document ownership and add v0.4 Work/cross-work tables."""
    inspector = sa_inspect(engine)
    indexes = {index["name"] for index in inspector.get_indexes("document")}
    has_new_index = "ix_document_work_id" in indexes
    indexed_topic_unique = any(
        "topic_id" in (index.get("column_names") or []) and index.get("unique", False)
        for index in inspector.get_indexes("document")
    )
    constrained_topic_unique = any(
        constraint.get("column_names") == ["topic_id"]
        for constraint in inspector.get_unique_constraints("document")
    )
    has_old_unique = indexed_topic_unique or constrained_topic_unique
    schema_ok = has_new_index and not has_old_unique

    if has_new_index and has_old_unique:
        logger.warning(
            "v0.4 migration: ix_document_work_id exists but topic_id UNIQUE "
            "still present — redoing table rebuild"
        )
        with engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_document_work_id"))
        schema_ok = False

    if not schema_ok:
        from models.work import Work

        SQLModel.metadata.create_all(engine, tables=[Work.__table__])  # type: ignore[arg-type]
        with engine.connect() as conn:
            raw = conn.connection.dbapi_connection
            foreign_keys_enabled = int(raw.execute("PRAGMA foreign_keys").fetchone()[0])
            raw.execute("PRAGMA foreign_keys = OFF")
            raw.execute("BEGIN")
            try:
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
                raw.execute("COMMIT")
            except Exception:
                raw.execute("ROLLBACK")
                raise
            finally:
                raw.execute(f"PRAGMA foreign_keys = {foreign_keys_enabled}")

        with engine.connect() as conn:
            violations = list(conn.connection.dbapi_connection.execute("PRAGMA foreign_key_check"))
            if violations:
                details = "; ".join(str(row) for row in violations[:10])
                logger.error("v0.4 migration FK violations: %s", details)
                raise RuntimeError(f"v0.4 migration failed: {len(violations)} FK violations")

    from models.cross_work_run import CrossWorkRun
    from models.entity_mention import EntityMention
    from models.global_entity import GlobalEntity
    from models.graph_snapshot import GraphSnapshot
    from models.timeline_item import TimelineItem
    from models.work import Work

    SQLModel.metadata.create_all(engine, tables=[Work.__table__])  # type: ignore[arg-type]
    SQLModel.metadata.create_all(
        engine,
        tables=[
            GlobalEntity.__table__,  # type: ignore[arg-type]
            EntityMention.__table__,  # type: ignore[arg-type]
            CrossWorkRun.__table__,  # type: ignore[arg-type]
            GraphSnapshot.__table__,  # type: ignore[arg-type]
            TimelineItem.__table__,  # type: ignore[arg-type]
        ],
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_document_work_id "
                "ON document(work_id) WHERE work_id IS NOT NULL"
            )
        )

    from services.work_service import backfill_all_null_work_ids

    with Session(engine) as session:
        count = backfill_all_null_work_ids(session)
        if count > 0:
            logger.info("v0.4 migration: backfilled %d documents with work_id", count)


def migrate_chat_message_linkage_columns(engine: Engine) -> None:
    """Add and deterministically backfill chat turn linkage and ordering."""
    add_missing_columns(
        engine,
        "chat_message",
        [
            ("turn_id", "TEXT"),
            ("reply_to_message_id", "TEXT"),
            ("sequence_index", "INTEGER"),
        ],
    )
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, session_id, role, turn_id, reply_to_message_id, "
                "sequence_index FROM chat_message ORDER BY session_id, created_at, rowid"
            )
        ).mappings()
        current_session: str | None = None
        sequence_index = 0
        pending_user_id: str | None = None
        pending_turn_id: str | None = None
        for row in rows:
            if row["session_id"] != current_session:
                current_session = row["session_id"]
                sequence_index = 0
                pending_user_id = None
                pending_turn_id = None
            turn_id = row["turn_id"]
            reply_to_message_id = row["reply_to_message_id"]
            if row["role"] == "user":
                sequence_index += 1
                turn_id = turn_id or row["id"]
                pending_user_id = row["id"]
                pending_turn_id = turn_id
            elif row["role"] == "assistant" and pending_user_id is not None:
                turn_id = turn_id or pending_turn_id
                reply_to_message_id = reply_to_message_id or pending_user_id
                pending_user_id = None
                pending_turn_id = None
            else:
                sequence_index += 1
                turn_id = turn_id or row["id"]
                pending_user_id = None
                pending_turn_id = None
            conn.execute(
                text(
                    "UPDATE chat_message SET turn_id = :turn_id, "
                    "reply_to_message_id = :reply_to_message_id, "
                    "sequence_index = :sequence_index WHERE id = :id"
                ),
                {
                    "id": row["id"],
                    "turn_id": turn_id,
                    "reply_to_message_id": reply_to_message_id,
                    "sequence_index": row["sequence_index"] or sequence_index,
                },
            )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_chat_message_turn_id ON chat_message(turn_id)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chat_message_session_sequence "
                "ON chat_message(session_id, sequence_index)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chat_message_reply_to_message_id "
                "ON chat_message(reply_to_message_id)"
            )
        )


def migrate_graph_snapshot_integrity(engine: Engine) -> None:
    """Remove persisted graph snapshots that cannot resolve to the live entity registry."""
    from models.global_entity import GlobalEntity
    from models.graph_snapshot import GraphSnapshot
    from services.cross_work_entity_service import graph_snapshot_references_are_valid

    with Session(engine) as session:
        snapshots = session.exec(
            select(GraphSnapshot).where(GraphSnapshot.graph_type == "character_relationship")
        ).all()
        live_ids_by_topic: dict[str, set[str]] = {}
        invalidated = 0
        for snapshot in snapshots:
            if snapshot.topic_id not in live_ids_by_topic:
                live_ids_by_topic[snapshot.topic_id] = set(
                    session.exec(
                        select(GlobalEntity.id).where(GlobalEntity.topic_id == snapshot.topic_id)
                    ).all()
                )
            if not graph_snapshot_references_are_valid(
                snapshot.nodes_json,
                snapshot.edges_json,
                live_ids_by_topic[snapshot.topic_id],
            ):
                session.delete(snapshot)
                invalidated += 1
        session.commit()
        if invalidated:
            logger.info(
                "graph snapshot integrity migration: invalidated %d snapshot(s)",
                invalidated,
            )


def migrate_topic_storage_totals(engine: Engine) -> None:
    """Recompute every Topic's cached source-document byte total."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE topic SET storage_bytes = COALESCE(("
                "SELECT SUM(COALESCE(document.file_size_bytes, 0)) "
                "FROM document WHERE document.topic_id = topic.id"
                "), 0)"
            )
        )


ORDERED_MIGRATIONS: tuple[Migration, ...] = (
    Migration("001_chat_usage", "Add chat token usage columns", migrate_chat_message_usage_columns),
    Migration(
        "002_analysis_output_run", "Link outputs to AnalysisRun", migrate_analysis_output_run_id
    ),
    Migration(
        "003_analysis_run_final", "Add final-stage counters", migrate_analysis_run_final_columns
    ),
    Migration(
        "004_analysis_artifact", "Create analysis artifact storage", migrate_analysis_artifact
    ),
    Migration(
        "005_source_locators", "Add v0.3 source locator columns", migrate_v03_source_locator_columns
    ),
    Migration("006_retrieval_trace", "Create retrieval trace storage", migrate_retrieval_trace),
    Migration("007_chunk_fts", "Create chunk FTS index", migrate_chunk_fts),
    Migration("008_embedding_cache", "Create embedding cache", migrate_embedding_cache),
    Migration(
        "009_extraction_usage",
        "Add extraction usage details",
        migrate_local_extraction_usage_columns,
    ),
    Migration(
        "010_work_schema", "Add Work ownership and cross-work tables", migrate_v04_work_tables
    ),
    Migration(
        "011_chat_linkage", "Add explicit chat turn linkage", migrate_chat_message_linkage_columns
    ),
    Migration(
        "012_graph_snapshot_integrity",
        "Remove malformed or dangling graph snapshots",
        migrate_graph_snapshot_integrity,
    ),
    Migration(
        "013_topic_storage_totals",
        "Backfill aggregate Topic source storage",
        migrate_topic_storage_totals,
    ),
)


def run_migrations(engine: Engine, migrations: Sequence[Migration] = ORDERED_MIGRATIONS) -> None:
    """Run every idempotent migration in declared order, stopping on failure."""
    for migration in migrations:
        logger.info("database migration %s: %s", migration.id, migration.description)
        migration.apply(engine)


def upgrade_schema(engine: Engine) -> None:
    """Create absent current tables, then upgrade every existing table in order."""
    configure_sqlite_engine(engine)
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)
