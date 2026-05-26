"""v0.3 Step 1 — Schema Foundation tests."""

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine


class TestDocumentChapterChunkNewColumns:
    def test_document_has_metadata_json(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("document")}
        assert "metadata_json" in cols

    def test_chapter_has_locator_fields(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("chapter")}
        assert "source_href" in cols
        assert "nav_order" in cols
        assert "metadata_json" in cols

    def test_chunk_has_source_locator_json(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("chunk")}
        assert "source_locator_json" in cols

    def test_new_columns_are_nullable(self, engine):
        inspector = inspect(engine)
        chunk_cols = {c["name"]: c["nullable"] for c in inspector.get_columns("chunk")}
        assert chunk_cols["source_locator_json"] is True

        chapter_cols = {c["name"]: c["nullable"] for c in inspector.get_columns("chapter")}
        assert chapter_cols["source_href"] is True
        assert chapter_cols["nav_order"] is True
        assert chapter_cols["metadata_json"] is True

    def test_txt_document_defaults_unchanged(self, engine):
        """Existing TXT documents should work with defaults."""
        from models.document import Document

        with Session(engine) as session:
            doc = Document(
                topic_id="t1",
                original_filename="test.txt",
                file_size_bytes=1000,
                char_count=500,
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

            assert doc.file_type == "txt"
            assert doc.encoding == "utf-8"
            assert doc.stored_filename == "original.txt"
            assert doc.metadata_json is None
            assert doc.status == "uploaded"


class TestRetrievalTraceModel:
    def test_table_exists(self, engine):
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "retrieval_trace" in table_names

    def test_create_and_read(self, engine):
        from models.retrieval_trace import RetrievalTrace

        with Session(engine) as session:
            trace = RetrievalTrace(
                topic_id="t1",
                query="test query",
                method="keyword",
                results_json='[{"chunk_id": "c1", "score": 10}]',
            )
            session.add(trace)
            session.commit()
            session.refresh(trace)

            assert trace.id is not None
            assert trace.topic_id == "t1"
            assert trace.query == "test query"
            assert trace.method == "keyword"
            assert trace.created_at is not None

    def test_nullable_session_and_message(self, engine):
        from models.retrieval_trace import RetrievalTrace

        with Session(engine) as session:
            trace = RetrievalTrace(
                topic_id="t1",
                query="q",
                method="fts",
                results_json="[]",
            )
            session.add(trace)
            session.commit()
            session.refresh(trace)

            assert trace.session_id is None
            assert trace.message_id is None


class TestFTSVirtualTable:
    def test_fts_table_created_after_migration_call(self, tmp_path):
        """ensure_chunk_fts_table creates the FTS virtual table."""
        db_path = tmp_path / "fts_test.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        # Need models imported so SQLModel knows about tables
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

        inspector = inspect(engine)
        # FTS5 tables appear differently in SQLite introspection.
        # The main table is chunk_fts; there are also internal
        # chunk_fts_content, chunk_fts_idx, etc.
        table_names = inspector.get_table_names()
        assert "chunk_fts" in table_names

    def test_fts_table_creation_is_idempotent(self, tmp_path):
        db_path = tmp_path / "fts_idem.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            # Second call must not raise
            ensure_chunk_fts_table(session)

    def test_fts_table_has_expected_columns(self, tmp_path):
        db_path = tmp_path / "fts_cols.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(chunk_fts)"))
            rows = result.fetchall()
            col_names = {row[1] for row in rows}
            assert "chunk_id" in col_names
            assert "topic_id" in col_names
            assert "title" in col_names
            assert "text" in col_names


class TestMigrationAddsColumnsToExistingDB:
    def _setup_old_schema_db(self, tmp_path):
        """Create a temporary DB with the OLD schema (no v0.3 columns),
        patch db.engine to point to it, insert a row of test data,
        and return the engine + the tmp db_path.

        All _migrate_* calls must happen AFTER this setup so they
        operate on the tmp engine, not the real global DB.
        """
        db_path = tmp_path / "old_schema.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")

        # Create tables via SQLModel — this gives us all registered tables
        # WITH the new v0.3 columns. To simulate an old DB, we then drop
        # the v0.3 columns with ALTER TABLE DROP COLUMN (SQLite 3.35+, 2021).
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        # Remove v0.3 columns to simulate pre-v0.3 schema
        drops = [
            ("document", "metadata_json"),
            ("chapter", "source_href"),
            ("chapter", "nav_order"),
            ("chapter", "metadata_json"),
            ("chunk", "source_locator_json"),
        ]
        with engine.connect() as conn:
            for table, col in drops:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {col}"))
            conn.commit()

        # Insert a minimal row into each table to verify data survives migration
        from uuid import uuid4

        topic_id = str(uuid4())
        doc_id = str(uuid4())
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO topic (id, name, storage_bytes, status, created_at, updated_at) "
                    "VALUES (:id, 'test', 0, 'created', '2025-01-01', '2025-01-01')"
                ),
                {"id": topic_id},
            )
            conn.execute(
                text(
                    "INSERT INTO document (id, topic_id, original_filename, stored_filename, "
                    "file_type, encoding, file_size_bytes, char_count, storage_path, status, "
                    "created_at, updated_at) "
                    "VALUES (:id, :tid, 'test.txt', 'original.txt', 'txt', 'utf-8', 1000, 500, "
                    "'', 'uploaded', '2025-01-01', '2025-01-01')"
                ),
                {"id": doc_id, "tid": topic_id},
            )
            conn.execute(
                text(
                    "INSERT INTO chapter (id, topic_id, document_id, chapter_index, title, "
                    "start_char, end_char, char_count, created_at) "
                    "VALUES (:id, :tid, :did, 0, 'Ch1', 0, 100, 100, '2025-01-01')"
                ),
                {"id": str(uuid4()), "tid": topic_id, "did": doc_id},
            )
            conn.execute(
                text(
                    "INSERT INTO chunk (id, topic_id, document_id, chunk_index, text, "
                    "start_char, end_char, char_count, estimated_tokens, created_at) "
                    "VALUES (:id, :tid, :did, 0, 'hello', 0, 5, 5, 3, '2025-01-01')"
                ),
                {"id": str(uuid4()), "tid": topic_id, "did": doc_id},
            )
            conn.commit()

        # Patch db.engine so all _migrate_* functions operate on the tmp engine
        import db as db_mod

        self._orig_engine = db_mod.engine
        db_mod.engine = engine
        self._test_engine = engine

        return topic_id, doc_id

    def teardown_method(self):
        """Restore the original db.engine after each test."""
        import db as db_mod

        if hasattr(self, "_orig_engine"):
            db_mod.engine = self._orig_engine

    def test_migration_adds_missing_columns(self, tmp_path):
        topic_id, doc_id = self._setup_old_schema_db(tmp_path)

        from db import _migrate_v03_source_locator_columns

        _migrate_v03_source_locator_columns()

        inspector = inspect(self._test_engine)
        doc_cols = {c["name"] for c in inspector.get_columns("document")}
        chapter_cols = {c["name"] for c in inspector.get_columns("chapter")}
        chunk_cols = {c["name"] for c in inspector.get_columns("chunk")}

        assert "metadata_json" in doc_cols
        assert "source_href" in chapter_cols
        assert "nav_order" in chapter_cols
        assert "metadata_json" in chapter_cols
        assert "source_locator_json" in chunk_cols

    def test_migration_preserves_old_data(self, tmp_path):
        topic_id, doc_id = self._setup_old_schema_db(tmp_path)

        from db import _migrate_v03_source_locator_columns

        _migrate_v03_source_locator_columns()

        with self._test_engine.connect() as conn:
            # Document row should still exist with original data
            doc = conn.execute(
                text("SELECT * FROM document WHERE id = :id"), {"id": doc_id}
            ).fetchone()
            assert doc is not None
            # New column should be NULL for existing row
            # (row is a tuple; find metadata_json by column name)
            col_names = conn.execute(text("PRAGMA table_info(document)")).fetchall()
            meta_idx = next(i for i, r in enumerate(col_names) if r[1] == "metadata_json")
            assert doc[meta_idx] is None  # old row gets NULL default

    def test_retrieval_trace_and_fts_on_patched_engine(self, tmp_path):
        self._setup_old_schema_db(tmp_path)

        from db import (
            _migrate_chunk_fts,
            _migrate_retrieval_trace,
            _migrate_v03_source_locator_columns,
        )

        _migrate_v03_source_locator_columns()
        _migrate_retrieval_trace()
        _migrate_chunk_fts()

        inspector = inspect(self._test_engine)
        assert "retrieval_trace" in inspector.get_table_names()
        assert "chunk_fts" in inspector.get_table_names()

    def test_migration_idempotent(self, tmp_path):
        self._setup_old_schema_db(tmp_path)

        from db import (
            _migrate_chunk_fts,
            _migrate_retrieval_trace,
            _migrate_v03_source_locator_columns,
        )

        # Run twice — must not raise
        _migrate_v03_source_locator_columns()
        _migrate_retrieval_trace()
        _migrate_chunk_fts()
        _migrate_v03_source_locator_columns()
        _migrate_retrieval_trace()
        _migrate_chunk_fts()
