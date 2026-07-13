from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlmodel import Session

from models.chat import ChatMessage, ChatSession
from services.chat_service import delete_chat_message, get_chat_messages


def test_explicit_linkage_orders_equal_timestamps_and_deletes_exact_reply(engine):
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        chat_session = ChatSession(topic_id="topic", title="Ordering")
        session.add(chat_session)
        session.flush()
        first_user = ChatMessage(
            id="user-b",
            session_id=chat_session.id,
            role="user",
            content="first",
            turn_id="turn-1",
            sequence_index=1,
            created_at=timestamp,
        )
        first_reply = ChatMessage(
            id="assistant-a",
            session_id=chat_session.id,
            role="assistant",
            content="first reply",
            turn_id="turn-1",
            reply_to_message_id=first_user.id,
            sequence_index=1,
            created_at=timestamp,
        )
        second_user = ChatMessage(
            id="user-a",
            session_id=chat_session.id,
            role="user",
            content="second",
            turn_id="turn-2",
            sequence_index=2,
            created_at=timestamp,
        )
        second_reply = ChatMessage(
            id="assistant-b",
            session_id=chat_session.id,
            role="assistant",
            content="second reply",
            turn_id="turn-2",
            reply_to_message_id=second_user.id,
            sequence_index=2,
            created_at=timestamp,
        )
        session.add_all([second_reply, first_reply, second_user, first_user])
        session.commit()

        assert [message.id for message in get_chat_messages(chat_session.id, session)] == [
            first_user.id,
            first_reply.id,
            second_user.id,
            second_reply.id,
        ]
        assert delete_chat_message(first_user.id, session)
        assert session.get(ChatMessage, first_user.id) is None
        assert session.get(ChatMessage, first_reply.id) is None
        assert session.get(ChatMessage, second_user.id) is not None
        assert session.get(ChatMessage, second_reply.id) is not None


def test_deleting_assistant_does_not_delete_another_assistant(engine):
    with Session(engine) as session:
        chat_session = ChatSession(topic_id="topic", title="Delete")
        session.add(chat_session)
        session.flush()
        first = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="orphan one",
            turn_id="turn-1",
            sequence_index=1,
        )
        second = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="orphan two",
            turn_id="turn-2",
            sequence_index=2,
        )
        session.add_all([first, second])
        session.commit()

        assert delete_chat_message(first.id, session)
        assert session.get(ChatMessage, second.id) is not None


def test_linkage_migration_backfills_legacy_rows_idempotently(tmp_path):
    from sqlmodel import create_engine

    from db import _migrate_chat_message_linkage_columns

    migration_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}")
    with migration_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE chat_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
                "role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_message (id, session_id, role, content, created_at) VALUES "
                "('u1', 's1', 'user', 'q', '2026-01-01'), "
                "('a1', 's1', 'assistant', 'a', '2026-01-02'), "
                "('a2', 's1', 'assistant', 'orphan', '2026-01-03'), "
                "('u2', 's2', 'user', 'q2', '2026-01-01')"
            )
        )

    _migrate_chat_message_linkage_columns(migration_engine)
    _migrate_chat_message_linkage_columns(migration_engine)

    columns = {column["name"] for column in inspect(migration_engine).get_columns("chat_message")}
    assert {"turn_id", "reply_to_message_id", "sequence_index"} <= columns
    with migration_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, turn_id, reply_to_message_id, sequence_index "
                "FROM chat_message ORDER BY session_id, sequence_index, id"
            )
        ).all()
    assert rows == [
        ("a1", "u1", "u1", 1),
        ("u1", "u1", None, 1),
        ("a2", "a2", None, 2),
        ("u2", "u2", None, 1),
    ]
