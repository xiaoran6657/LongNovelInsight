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
                conn.execute(
                    text(f"ALTER TABLE chat_message ADD COLUMN {col_name} {col_def}")
                )
            except Exception:
                pass  # column already exists
        conn.commit()


def _migrate_analysis_output_run_id() -> None:
    """Add run_id column to analysis_output if it doesn't exist yet."""
    with engine.connect() as conn:
        try:
            conn.execute(
                text("ALTER TABLE analysis_output ADD COLUMN run_id TEXT")
            )
        except Exception:
            pass
        conn.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_chat_message_usage_columns()
    _migrate_analysis_output_run_id()
