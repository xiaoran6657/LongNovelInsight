"""Database engine, sessions, schema creation, and ordered migration startup."""

from collections.abc import Generator

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

import models  # noqa: F401 — ensure all table models register with SQLModel.metadata
from config import DATA_DIR, DB_PATH
from migrations import (
    migrate_analysis_artifact,
    migrate_analysis_output_run_id,
    migrate_analysis_run_final_columns,
    migrate_chat_message_linkage_columns,
    migrate_chat_message_usage_columns,
    migrate_chunk_fts,
    migrate_embedding_cache,
    migrate_local_extraction_usage_columns,
    migrate_retrieval_trace,
    migrate_v03_source_locator_columns,
    migrate_v04_work_tables,
    upgrade_schema,
)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# Compatibility aliases for focused legacy tests and local maintenance commands.
# New orchestration uses migrations.run_migrations and passes an Engine explicitly.
def _migrate_chat_message_usage_columns() -> None:
    migrate_chat_message_usage_columns(engine)


def _migrate_chat_message_linkage_columns(_engine: Engine | None = None) -> None:
    migrate_chat_message_linkage_columns(_engine or engine)


def _migrate_analysis_output_run_id() -> None:
    migrate_analysis_output_run_id(engine)


def _migrate_analysis_run_final_columns() -> None:
    migrate_analysis_run_final_columns(engine)


def _migrate_analysis_artifact() -> None:
    migrate_analysis_artifact(engine)


def _migrate_v03_source_locator_columns() -> None:
    migrate_v03_source_locator_columns(engine)


def _migrate_retrieval_trace() -> None:
    migrate_retrieval_trace(engine)


def _migrate_chunk_fts() -> None:
    migrate_chunk_fts(engine)


def _migrate_embedding_cache() -> None:
    migrate_embedding_cache(engine)


def _migrate_local_extraction_usage_columns() -> None:
    migrate_local_extraction_usage_columns(engine)


def _migrate_v04_work_tables(_engine: Engine | None = None) -> None:
    migrate_v04_work_tables(_engine or engine)


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    upgrade_schema(engine)
