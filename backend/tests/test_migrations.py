"""End-to-end tests for the ordered database migration registry."""

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from migrations import ORDERED_MIGRATIONS, Migration, run_migrations, upgrade_schema


def _legacy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    statements = [
        """CREATE TABLE topic (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            provider_id TEXT, storage_bytes INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'created', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE document (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL UNIQUE REFERENCES topic(id),
            original_filename TEXT NOT NULL, stored_filename TEXT NOT NULL DEFAULT 'original.txt',
            file_type TEXT NOT NULL DEFAULT 'txt', content_type TEXT,
            encoding TEXT NOT NULL DEFAULT 'utf-8', file_size_bytes INTEGER NOT NULL DEFAULT 0,
            char_count INTEGER NOT NULL DEFAULT 0, storage_path TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'uploaded', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE chapter (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topic(id),
            document_id TEXT NOT NULL REFERENCES document(id), chapter_index INTEGER NOT NULL,
            title TEXT NOT NULL, start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
            char_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        )""",
        """CREATE TABLE chunk (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topic(id),
            document_id TEXT NOT NULL REFERENCES document(id),
            chapter_id TEXT REFERENCES chapter(id), chunk_index INTEGER NOT NULL,
            chapter_index INTEGER, text TEXT NOT NULL DEFAULT '', start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL, char_count INTEGER NOT NULL DEFAULT 0,
            estimated_tokens INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        )""",
        """CREATE TABLE chat_session (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topic(id), title TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE chat_message (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES chat_session(id),
            role TEXT NOT NULL, content TEXT NOT NULL, evidence_json TEXT, uncertainty TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE analysis_run (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topic(id), job_id TEXT,
            mode TEXT NOT NULL DEFAULT 'preview', status TEXT NOT NULL DEFAULT 'pending',
            requested_types_json TEXT NOT NULL DEFAULT '[]', chunk_selection_json TEXT NOT NULL DEFAULT '{}',
            effective_config_json TEXT NOT NULL DEFAULT '{}', progress_current INTEGER NOT NULL DEFAULT 0,
            progress_total INTEGER NOT NULL DEFAULT 0, extraction_total INTEGER NOT NULL DEFAULT 0,
            extraction_succeeded INTEGER NOT NULL DEFAULT 0, extraction_failed INTEGER NOT NULL DEFAULT 0,
            merge_total INTEGER NOT NULL DEFAULT 0, merge_succeeded INTEGER NOT NULL DEFAULT 0,
            merge_failed INTEGER NOT NULL DEFAULT 0, prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0,
            model_used TEXT, error_message TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE analysis_output (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topic(id), job_id TEXT,
            output_type TEXT NOT NULL, title TEXT NOT NULL, content_json TEXT NOT NULL,
            source_chunk_ids TEXT NOT NULL DEFAULT '[]', evidence_quotes TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0, prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE local_extraction (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_run(id),
            topic_id TEXT NOT NULL REFERENCES topic(id), chunk_id TEXT NOT NULL REFERENCES chunk(id),
            status TEXT NOT NULL DEFAULT 'pending', attempt_count INTEGER NOT NULL DEFAULT 0,
            content_json TEXT, source_chunk_ids TEXT NOT NULL DEFAULT '[]',
            evidence_quotes TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0, model_used TEXT, error_message TEXT,
            started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(
            text(
                "INSERT INTO topic VALUES "
                "('t1', 'Legacy Topic', NULL, NULL, 0, 'parsed', '2025-01-01', '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO document VALUES "
                "('d1', 't1', 'legacy.txt', 'original.txt', 'txt', 'text/plain', 'utf-8', "
                "100, 90, 'topics/t1/source/original.txt', 'parsed', '2025-01-01', '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chapter VALUES "
                "('ch1', 't1', 'd1', 0, 'Legacy Chapter', 0, 90, 90, '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chunk VALUES "
                "('c1', 't1', 'd1', 'ch1', 0, 0, 'legacy text', 0, 90, 90, 60, '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_session VALUES "
                "('s1', 't1', 'Legacy Chat', '2025-01-01', '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_message VALUES "
                "('u1', 's1', 'user', 'question', NULL, NULL, '2025-01-01T00:00:00'), "
                "('a1', 's1', 'assistant', 'answer', NULL, NULL, '2025-01-01T00:00:01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO analysis_run VALUES "
                "('r1', 't1', NULL, 'preview', 'succeeded', '[]', '{}', '{}', 1, 1, 1, 1, 0, "
                "1, 1, 0, 10, 5, 15, 'legacy-model', NULL, '{}', '2025-01-01', '2025-01-01', "
                "'2025-01-01', '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO analysis_output VALUES "
                "('o1', 't1', NULL, 'characters', 'Legacy Output', '{\"characters\":[]}', "
                "'[\"c1\"]', '[\"legacy text\"]', 0.8, 10, 5, '2025-01-01', '2025-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO local_extraction VALUES "
                "('e1', 'r1', 't1', 'c1', 'succeeded', 1, '{}', '[\"c1\"]', "
                "'[\"legacy text\"]', 0.8, 10, 5, 15, 'legacy-model', NULL, '2025-01-01', "
                "'2025-01-01', '2025-01-01', '2025-01-01')"
            )
        )
    return engine


def _pre_patch_v040_engine(tmp_path):
    """Create current-schema rows with data corruption produced by the v0.4.0 services."""
    import models  # noqa: F401
    from models.document import Document
    from models.global_entity import GlobalEntity
    from models.graph_snapshot import GraphSnapshot
    from models.topic import Topic
    from models.work import Work

    engine = create_engine(f"sqlite:///{tmp_path / 'pre_patch_v040.sqlite'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_document_work_id "
                "ON document(work_id) WHERE work_id IS NOT NULL"
            )
        )
    with Session(engine) as session:
        topic = Topic(id="t-v040", name="Pre-patch Topic", storage_bytes=1)
        work_one = Work(id="w-v040-1", topic_id=topic.id, title="One", series_index=1)
        work_two = Work(id="w-v040-2", topic_id=topic.id, title="Two", series_index=2)
        session.add(topic)
        session.add(work_one)
        session.add(work_two)
        session.add(
            Document(
                id="d-v040-1",
                topic_id=topic.id,
                work_id=work_one.id,
                original_filename="one.txt",
                file_size_bytes=100,
            )
        )
        session.add(
            Document(
                id="d-v040-2",
                topic_id=topic.id,
                work_id=work_two.id,
                original_filename="two.epub",
                file_type="epub",
                file_size_bytes=250,
            )
        )
        for entity_id, name in (("live-a", "Alice"), ("live-b", "Bob")):
            session.add(
                GlobalEntity(
                    id=entity_id,
                    topic_id=topic.id,
                    entity_type="character",
                    canonical_name=name,
                )
            )
        session.add_all(
            (
                GraphSnapshot(
                    id="valid",
                    topic_id=topic.id,
                    graph_type="character_relationship",
                    nodes_json='[{"id":"live-a"},{"id":"live-b"}]',
                    edges_json='[{"source":"live-a","target":"live-b"}]',
                ),
                GraphSnapshot(
                    id="dangling",
                    topic_id=topic.id,
                    graph_type="character_relationship",
                    nodes_json='[{"id":"removed-a"}]',
                    edges_json="[]",
                ),
                GraphSnapshot(
                    id="missing-node-id",
                    topic_id=topic.id,
                    graph_type="character_relationship",
                    nodes_json="[{}]",
                    edges_json="[]",
                ),
                GraphSnapshot(
                    id="missing-edge-target",
                    topic_id=topic.id,
                    graph_type="character_relationship",
                    nodes_json='[{"id":"live-a"}]',
                    edges_json='[{"source":"live-a"}]',
                ),
                GraphSnapshot(
                    id="endpoint-not-in-nodes",
                    topic_id=topic.id,
                    graph_type="character_relationship",
                    nodes_json='[{"id":"live-a"}]',
                    edges_json='[{"source":"live-a","target":"live-b"}]',
                ),
            )
        )
        session.commit()
    return engine


def test_registry_ids_are_unique_and_ordered():
    ids = [migration.id for migration in ORDERED_MIGRATIONS]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)
    assert ids.index("005_source_locators") < ids.index("010_work_schema")
    assert ids.index("010_work_schema") < ids.index("012_graph_snapshot_integrity")
    assert ids.index("012_graph_snapshot_integrity") < ids.index("013_topic_storage_totals")


def test_runner_preserves_order_and_stops_on_failure(engine):
    calls: list[str] = []

    def succeed(_engine):
        calls.append("first")

    def fail(_engine):
        calls.append("second")
        raise RuntimeError("migration failed")

    def must_not_run(_engine):
        calls.append("third")

    migrations = (
        Migration("001", "first", succeed),
        Migration("002", "second", fail),
        Migration("003", "third", must_not_run),
    )

    import pytest

    with pytest.raises(RuntimeError, match="migration failed"):
        run_migrations(engine, migrations)
    assert calls == ["first", "second"]


def test_full_legacy_upgrade_is_idempotent_and_preserves_data(tmp_path):
    engine = _legacy_engine(tmp_path)

    upgrade_schema(engine)
    upgrade_schema(engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {
        "analysis_artifact",
        "embedding_cache",
        "retrieval_trace",
        "work",
        "global_entity",
        "entity_mention",
        "cross_work_run",
        "graph_snapshot",
        "timeline_item",
        "chunk_fts",
    } <= tables

    expected_columns = {
        "document": {"metadata_json", "work_id"},
        "chapter": {"source_href", "nav_order", "metadata_json"},
        "chunk": {"source_locator_json"},
        "chat_message": {
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "model_used",
            "turn_id",
            "reply_to_message_id",
            "sequence_index",
        },
        "analysis_output": {"run_id"},
        "analysis_run": {"final_total", "final_succeeded", "final_failed", "final_skipped"},
        "local_extraction": {
            "reasoning_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "usage_unavailable_attempts",
            "attempt_usage_json",
        },
    }
    for table, columns in expected_columns.items():
        assert columns <= {column["name"] for column in inspector.get_columns(table)}

    assert not any(
        constraint.get("column_names") == ["topic_id"]
        for constraint in inspector.get_unique_constraints("document")
    )
    assert "ix_document_work_id" in {index["name"] for index in inspector.get_indexes("document")}

    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        document = conn.execute(
            text("SELECT topic_id, work_id, original_filename FROM document WHERE id = 'd1'")
        ).one()
        assert document.topic_id == "t1"
        assert document.work_id is not None
        assert document.original_filename == "legacy.txt"
        assert (
            conn.execute(text("SELECT count(*) FROM work WHERE topic_id = 't1'")).scalar_one() == 1
        )
        assert conn.execute(text("SELECT title FROM chapter WHERE id = 'ch1'")).scalar_one() == (
            "Legacy Chapter"
        )
        assert conn.execute(text("SELECT text FROM chunk WHERE id = 'c1'")).scalar_one() == (
            "legacy text"
        )
        chat = conn.execute(
            text(
                "SELECT turn_id, reply_to_message_id, sequence_index "
                "FROM chat_message WHERE id = 'a1'"
            )
        ).one()
        assert chat == ("u1", "u1", 1)
        assert conn.execute(
            text("SELECT content_json FROM analysis_output WHERE id = 'o1'")
        ).scalar_one() == ('{"characters":[]}')
        assert (
            conn.execute(text("SELECT final_total FROM analysis_run WHERE id = 'r1'")).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT reasoning_tokens FROM local_extraction WHERE id = 'e1'")
            ).scalar_one()
            == 0
        )
        assert list(conn.execute(text("PRAGMA foreign_key_check"))) == []


def test_pre_patch_v040_upgrade_repairs_graphs_and_storage_idempotently(tmp_path):
    from models.graph_snapshot import GraphSnapshot
    from models.topic import Topic

    engine = _pre_patch_v040_engine(tmp_path)

    upgrade_schema(engine)
    upgrade_schema(engine)

    with Session(engine) as session:
        topic = session.get(Topic, "t-v040")
        assert topic is not None
        assert topic.storage_bytes == 350
        snapshot_ids = set(session.exec(select(GraphSnapshot.id)).all())
        assert snapshot_ids == {"valid"}
