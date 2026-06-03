"""Tests for v0.4 multi-Work schema migration."""

from sqlmodel import Session, select

from models.document import Document
from models.topic import Topic
from models.work import Work


def test_work_table_exists(engine):
    """work table should be created by init_db."""
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(engine)
    tables = insp.get_table_names()
    assert "work" in tables


def test_document_work_id_column_exists(engine):
    """document.work_id column should exist after migration."""
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(engine)
    cols = {c["name"] for c in insp.get_columns("document")}
    assert "work_id" in cols


def test_ix_document_work_id_exists(engine):
    """Partial unique index on document(work_id) should exist after migration."""
    from sqlalchemy import inspect as sa_inspect

    from db import _migrate_v04_work_tables

    _migrate_v04_work_tables(_engine=engine)

    insp = sa_inspect(engine)
    indexes = {i["name"] for i in insp.get_indexes("document")}
    assert "ix_document_work_id" in indexes


def test_all_v04_tables_exist(engine):
    """All 6 new v0.4 tables should exist."""
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(engine)
    tables = set(insp.get_table_names())
    for name in (
        "work",
        "global_entity",
        "entity_mention",
        "cross_work_run",
        "graph_snapshot",
        "timeline_item",
    ):
        assert name in tables, f"Table '{name}' not found"


def test_legacy_topic_gets_default_work(engine):
    """Topic with Document but no Work → default Work created, document.work_id set."""
    from models.model_provider import ModelProvider

    # Setup: Topic + Document without explicit Work
    with Session(engine) as session:
        prov = ModelProvider(
            name="MigProv", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="MigrationTest", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="novel.txt",
            file_size_bytes=100, char_count=50, status="parsed",
            work_id=None,
        )
        session.add(doc)
        session.commit()
        tid = topic.id
        did = doc.id

    # Run migration directly on the test engine
    from db import _migrate_v04_work_tables
    _migrate_v04_work_tables(_engine=engine)

    # Verify
    with Session(engine) as session:
        doc = session.get(Document, did)
        assert doc is not None
        assert doc.work_id is not None, "document.work_id should be backfilled"

        work = session.get(Work, doc.work_id)
        assert work is not None
        assert work.topic_id == tid
        assert work.series_index == 1
        assert work.title == "novel"


def test_migration_idempotent(engine):
    """Running migration twice should not create duplicate Works."""
    from models.model_provider import ModelProvider

    with Session(engine) as session:
        prov = ModelProvider(
            name="IdemP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="IdemTopic", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="book.epub",
            file_size_bytes=200, char_count=100, status="parsed",
            work_id=None,
        )
        session.add(doc)
        session.commit()
        tid = topic.id

    from db import _migrate_v04_work_tables

    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        count_before = len(session.exec(select(Work).where(Work.topic_id == tid)).all())

    # Run migration again — idempotent
    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        count_after = len(session.exec(select(Work).where(Work.topic_id == tid)).all())
        assert count_after == count_before, "Migration should be idempotent"


def test_topic_without_document_no_work_created(engine):
    """Topic with no Document should not get a default Work."""
    with Session(engine) as session:
        topic = Topic(name="EmptyTopic", status="created")
        session.add(topic)
        session.commit()
        tid = topic.id

    from db import _migrate_v04_work_tables
    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        works = session.exec(select(Work).where(Work.topic_id == tid)).all()
        assert len(works) == 0


def test_document_can_have_null_work_id(engine):
    """Newly uploaded documents without a Work should allow work_id=NULL."""
    from models.model_provider import ModelProvider

    with Session(engine) as session:
        prov = ModelProvider(
            name="NullWIdP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="NullWId", provider_id=prov.id, status="uploaded")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="test.txt",
            file_size_bytes=10, char_count=10,
            work_id=None,
        )
        session.add(doc)
        session.commit()

        assert doc.id is not None
        assert doc.work_id is None


def test_topic_id_unique_constraint_removed(engine):
    """After migration, document.topic_id should NOT have a UNIQUE constraint."""
    from db import _migrate_v04_work_tables

    _migrate_v04_work_tables(_engine=engine)

    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(engine)
    indexes = list(insp.get_indexes("document"))
    topic_id_uniques = [
        i
        for i in indexes
        if "topic_id" in (i.get("column_names") or []) and i.get("unique", False)
    ]
    assert len(topic_id_uniques) == 0, (
        f"topic_id UNIQUE constraint still present: {topic_id_uniques}"
    )


def test_two_works_can_each_have_document_same_topic(engine):
    """After migration, two different Works in the same Topic can each have a Document."""
    from db import _migrate_v04_work_tables
    from models.model_provider import ModelProvider

    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        prov = ModelProvider(
            name="MultiDocP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="MultiDoc", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()

        w1 = Work(topic_id=topic.id, title="Book 1", series_index=1, status="parsed")
        w2 = Work(topic_id=topic.id, title="Book 2", series_index=2, status="parsed")
        session.add(w1); session.add(w2); session.flush()

        d1 = Document(
            topic_id=topic.id, work_id=w1.id, original_filename="book1.txt",
            file_size_bytes=100, char_count=50, status="parsed",
        )
        d2 = Document(
            topic_id=topic.id, work_id=w2.id, original_filename="book2.epub",
            file_size_bytes=200, char_count=100, status="parsed",
        )
        session.add(d1); session.add(d2)
        session.commit()

        assert d1.id is not None
        assert d2.id is not None
        assert d1.work_id == w1.id
        assert d2.work_id == w2.id


def test_same_work_second_document_rejected(engine):
    """Partial unique index should reject a second Document for the same Work."""
    from db import _migrate_v04_work_tables
    from models.model_provider import ModelProvider

    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        prov = ModelProvider(
            name="DupWorkDocP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="DupWorkDoc", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        work = Work(topic_id=topic.id, title="Only Book", series_index=1)
        session.add(work); session.flush()

        d1 = Document(
            topic_id=topic.id, work_id=work.id, original_filename="book.txt",
            file_size_bytes=100, char_count=50, status="parsed",
        )
        session.add(d1); session.commit()

        # Second document with same work_id should violate the partial unique index
        import pytest

        d2 = Document(
            topic_id=topic.id, work_id=work.id, original_filename="book2.txt",
            file_size_bytes=100, char_count=50, status="parsed",
        )
        session.add(d2)
        with pytest.raises(Exception) as exc_info:
            session.commit()
        assert "UNIQUE" in str(exc_info.value).upper() or "ix_document_work_id" in str(exc_info.value)


def test_fk_integrity_after_migration(engine):
    """PRAGMA foreign_key_check should return zero rows after migration."""
    from db import _migrate_v04_work_tables
    from models.model_provider import ModelProvider

    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        prov = ModelProvider(
            name="FKCheckP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="FKCheck", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        work = Work(topic_id=topic.id, title="FK Book", series_index=1)
        session.add(work); session.flush()
        doc = Document(
            topic_id=topic.id, work_id=work.id, original_filename="fk.txt",
            file_size_bytes=10, char_count=10, status="parsed",
        )
        session.add(doc)
        session.commit()

    # Raw FK check
    with engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        fk_result = list(raw.execute("PRAGMA foreign_key_check"))
        assert len(fk_result) == 0, f"FK violations found: {fk_result[:5]}"


def test_broken_state_repair(engine):
    """If ix_document_work_id exists but topic_id UNIQUE still present,
    migration should drop the partial index and redo the table rebuild."""
    from db import _migrate_v04_work_tables

    # First, run the migration normally
    _migrate_v04_work_tables(_engine=engine)

    # Now simulate broken state: manually recreate the old UNIQUE constraint
    with engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        # Create a unique index mimicking the old topic_id UNIQUE
        try:
            raw.execute(
                "CREATE UNIQUE INDEX broken_topic_id_unique ON document(topic_id)"
            )
        except Exception:
            pass  # may already exist in some form

    # Verify broken state
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(engine)
    indexes = list(insp.get_indexes("document"))
    topic_id_uniques = [
        i
        for i in indexes
        if "topic_id" in (i.get("column_names") or []) and i.get("unique", False)
    ]
    assert len(topic_id_uniques) > 0, "test setup: should have topic_id UNIQUE"

    # Run migration again — should repair
    _migrate_v04_work_tables(_engine=engine)

    # Verify repaired
    insp = sa_inspect(engine)
    indexes = list(insp.get_indexes("document"))
    topic_id_uniques = [
        i
        for i in indexes
        if "topic_id" in (i.get("column_names") or []) and i.get("unique", False)
    ]
    assert len(topic_id_uniques) == 0, "broken state should be repaired"


def test_backfill_after_schema_migrated(engine):
    """Schema migrated, then new NULL-work_id document appears — migration should backfill."""
    from db import _migrate_v04_work_tables
    from models.model_provider import ModelProvider

    # First run: schema + default Work backfill
    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        prov = ModelProvider(
            name="LateBackfillP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="LateBackfill", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()

        # Insert a Document with work_id=NULL (simulating a document that predates
        # Work creation, or was created without a Work)
        doc = Document(
            topic_id=topic.id, original_filename="late.txt",
            file_size_bytes=100, char_count=50, status="parsed",
            work_id=None,
        )
        session.add(doc)
        session.commit()
        did = doc.id

    # Second run: schema is OK, should still backfill the NULL work_id
    _migrate_v04_work_tables(_engine=engine)

    with Session(engine) as session:
        doc = session.get(Document, did)
        assert doc is not None
        assert doc.work_id is not None, (
            "NULL work_id should be backfilled even when schema is already migrated"
        )


def test_get_or_create_default_work_creates_work(engine):
    """Legacy Topic + Document → helper creates default Work and backfills document."""
    from models.model_provider import ModelProvider

    with Session(engine) as session:
        prov = ModelProvider(
            name="HelperP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="HelperTopic", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="helper_novel.txt",
            file_size_bytes=100, char_count=50, status="parsed",
            work_id=None,
        )
        session.add(doc)
        session.commit()
        tid = topic.id

        from services.work_service import get_or_create_default_work

        work = get_or_create_default_work(tid, session)
        assert work is not None
        assert work.topic_id == tid
        assert work.series_index == 1
        assert work.title == "helper_novel"

        # Document should be backfilled
        session.refresh(doc)
        assert doc.work_id == work.id


def test_get_or_create_default_work_idempotent(engine):
    """Calling the helper twice should return the same Work, not create a duplicate."""
    from models.model_provider import ModelProvider

    with Session(engine) as session:
        prov = ModelProvider(
            name="IdemHelperP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="IdemHelper", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="idem_novel.txt",
            file_size_bytes=100, char_count=50, status="parsed",
            work_id=None,
        )
        session.add(doc)
        session.commit()
        tid = topic.id

        from services.work_service import get_or_create_default_work

        w1 = get_or_create_default_work(tid, session)
        w2 = get_or_create_default_work(tid, session)

        assert w1.id == w2.id
        # Only one Work row
        works = session.exec(select(Work).where(Work.topic_id == tid)).all()
        assert len(works) == 1


def test_get_or_create_default_work_empty_topic_raises(engine):
    """Topic with no Document → helper should raise 404."""
    with Session(engine) as session:
        topic = Topic(name="EmptyHelper", status="created")
        session.add(topic)
        session.commit()
        tid = topic.id

        import pytest
        from fastapi import HTTPException

        from services.work_service import get_or_create_default_work

        with pytest.raises(HTTPException) as exc_info:
            get_or_create_default_work(tid, session)
        assert exc_info.value.status_code == 404
