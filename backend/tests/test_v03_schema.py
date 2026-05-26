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
        chunk_cols = {
            c["name"]: c["nullable"] for c in inspector.get_columns("chunk")
        }
        assert chunk_cols["source_locator_json"] is True

        chapter_cols = {
            c["name"]: c["nullable"] for c in inspector.get_columns("chapter")
        }
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
    def test_alter_table_migration_does_not_fail_on_fresh_db(self, tmp_path):
        """The migration functions should be safe to call on a fresh DB."""
        db_path = tmp_path / "migrate_test.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401
        SQLModel.metadata.create_all(engine)

        # Simulate init_db by calling the migrations explicitly
        from db import (
            _migrate_chunk_fts,
            _migrate_retrieval_trace,
            _migrate_v03_source_locator_columns,
        )

        _migrate_v03_source_locator_columns()
        # patch engine to our tmp engine
        import db as db_mod

        orig_engine = db_mod.engine
        db_mod.engine = engine
        try:
            _migrate_retrieval_trace()
            _migrate_chunk_fts()
        finally:
            db_mod.engine = orig_engine

        # Columns should exist
        inspector = inspect(engine)
        doc_cols = {c["name"] for c in inspector.get_columns("document")}
        assert "metadata_json" in doc_cols
