import json

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, AtomType, JobStatus
from models.extracted_atom import ExtractedAtom
from models.local_extraction import LocalExtraction

# ── AnalysisRun JSON helpers ──


def test_analysis_run_set_get_requested_types():
    run = AnalysisRun()
    run.set_requested_types(["overview", "characters", "events"])
    assert run.get_requested_types() == ["overview", "characters", "events"]


def test_analysis_run_requested_types_empty():
    run = AnalysisRun()
    assert run.get_requested_types() == []


def test_analysis_run_chunk_selection():
    run = AnalysisRun()
    data = {"mode": "preview", "limit_chunks": 3}
    run.set_chunk_selection(data)
    assert run.get_chunk_selection() == data


def test_analysis_run_effective_config():
    run = AnalysisRun()
    config = {"model_name": "deepseek-v4-flash", "temperature": 0.1}
    run.set_effective_config(config)
    assert run.get_effective_config() == config


def test_analysis_run_metadata():
    run = AnalysisRun()
    meta = {"stage_timings": {"extraction": 12.3}, "warnings": []}
    run.set_metadata(meta)
    assert run.get_metadata() == meta


def test_analysis_run_defaults():
    run = AnalysisRun()
    assert run.status == JobStatus.PENDING
    assert run.mode == AnalysisMode.PREVIEW
    assert run.progress_current == 0
    assert run.prompt_tokens == 0


def test_analysis_run_json_corrupt_returns_empty():
    run = AnalysisRun(requested_types_json="not json", chunk_selection_json="{")
    assert run.get_requested_types() == []
    assert run.get_chunk_selection() == {}


# ── CRUD via session ──


def test_create_analysis_run(client):
    """Create a topic and an AnalysisRun."""
    r = client.post(
        "/api/topics",
        json={"name": "Run Test Topic", "description": "for run testing"},
    )
    assert r.status_code == 201
    topic_id = r.json()["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id, mode=AnalysisMode.PREVIEW)
        run.set_requested_types(["overview", "characters"])
        run.set_chunk_selection({"limit_chunks": 3})
        session.add(run)
        session.commit()
        session.refresh(run)

        assert run.id is not None
        assert run.topic_id == topic_id
        assert run.mode == "preview"
        assert run.status == "pending"
        assert run.get_requested_types() == ["overview", "characters"]

    # Cleanup
    client.delete(f"/api/topics/{topic_id}")


def test_create_local_extraction_and_atoms(client):
    """Create AnalysisRun → LocalExtraction → ExtractedAtom chain."""
    r = client.post("/api/topics", json={"name": "Extraction Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    # Need a chunk to reference
    import io

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={
            "file": (
                "novel.txt",
                io.BytesIO("第一章\n测试内容。\n第二章\n更多内容。\n".encode("utf-8")),
                "text/plain",
            )
        },
    )
    parse_resp = client.post(f"/api/topics/{topic_id}/parse")
    assert parse_resp.status_code == 200
    chunk_count = parse_resp.json()["chunk_count"]
    assert chunk_count > 0

    chunks_resp = client.get(f"/api/topics/{topic_id}/chunks?limit=1")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()["chunks"]
    assert len(chunks) == 1
    chunk_id = chunks[0]["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id, mode=AnalysisMode.PREVIEW)
        run.set_requested_types(["characters", "events"])
        session.add(run)
        session.flush()

        # Create local extraction
        ext = LocalExtraction(
            run_id=run.id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            status="succeeded",
            attempt_count=1,
            content_json=json.dumps({"local_characters": [], "local_events": []}),
            source_chunk_ids=json.dumps([chunk_id]),
            evidence_quotes=json.dumps(["测试证据"]),
            confidence=0.85,
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            model_used="deepseek-v4-flash",
        )
        session.add(ext)
        session.flush()

        # Create extracted atom
        atom = ExtractedAtom(
            run_id=run.id,
            topic_id=topic_id,
            local_extraction_id=ext.id,
            chunk_id=chunk_id,
            atom_type=AtomType.CHARACTER,
            stable_id="character_test_01",
            canonical_name="测试角色",
            content_json=json.dumps({"name": "测试角色", "traits": ["勇敢"]}),
            source_chunk_ids=json.dumps([chunk_id]),
            evidence_quotes=json.dumps(["测试证据"]),
            confidence=0.9,
            chapter_index=0,
            chunk_index=0,
        )
        session.add(atom)
        session.commit()
        session.refresh(atom)

        assert atom.id is not None
        assert atom.run_id == run.id
        assert atom.atom_type == "character"
        assert atom.stable_id == "character_test_01"
        assert atom.confidence == 0.9

    client.delete(f"/api/topics/{topic_id}")


def test_local_extraction_status_failed(client):
    """LocalExtraction with failed status and error message."""
    r = client.post("/api/topics", json={"name": "Failed Extraction"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    import io

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={
            "file": ("novel.txt", io.BytesIO("第一章\n测试。\n".encode("utf-8")), "text/plain")
        },
    )
    parse_resp = client.post(f"/api/topics/{topic_id}/parse")
    assert parse_resp.status_code == 200

    chunks_resp = client.get(f"/api/topics/{topic_id}/chunks?limit=1")
    chunks = chunks_resp.json()["chunks"]
    chunk_id = chunks[0]["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id)
        session.add(run)
        session.flush()

        ext = LocalExtraction(
            run_id=run.id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            status="failed",
            attempt_count=2,
            error_message="JSON parse failed",
        )
        session.add(ext)
        session.commit()
        session.refresh(ext)

        assert ext.status == "failed"
        assert ext.error_message == "JSON parse failed"
        assert ext.attempt_count == 2

    client.delete(f"/api/topics/{topic_id}")


def test_extracted_atom_all_types():
    """Each AtomType enum value can be stored."""
    for atom_type in AtomType:
        atom = ExtractedAtom(
            atom_type=atom_type,
            stable_id=f"test_{atom_type}_01",
            content_json="{}",
            source_chunk_ids="[]",
            evidence_quotes="[]",
        )
        assert atom.atom_type in {t.value for t in AtomType}


def test_analysis_run_status_transitions(client):
    """Run status transitions: pending → running → succeeded."""
    r = client.post("/api/topics", json={"name": "Status Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id)
        assert run.status == JobStatus.PENDING

        run.status = JobStatus.RUNNING
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.status == "running"

        run.status = JobStatus.SUCCEEDED
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.status == "succeeded"

    client.delete(f"/api/topics/{topic_id}")


def test_analysis_run_partial_success(client):
    """Partial success: some extractions failed but run can still be partial_success."""
    r = client.post("/api/topics", json={"name": "Partial Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(
            topic_id=topic_id,
            status=JobStatus.PARTIAL_SUCCESS,
            extraction_total=10,
            extraction_succeeded=8,
            extraction_failed=2,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.status == "partial_success"
        assert run.extraction_failed == 2

    client.delete(f"/api/topics/{topic_id}")


def test_migration_adds_run_id_to_analysis_output(client):
    """After migration, old AnalysisOutput rows have run_id=NULL and new writes work."""
    r = client.post("/api/topics", json={"name": "Migration Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        # Old-style output (no run_id)
        old = AnalysisOutput(
            topic_id=topic_id,
            output_type="overview",
            title="Old output",
            content_json="{}",
            source_chunk_ids="[]",
            evidence_quotes="[]",
        )
        session.add(old)
        session.commit()
        session.refresh(old)
        assert old.run_id is None  # nullable, backward-compatible

        # New-style output with run_id
        run = AnalysisRun(topic_id=topic_id)
        session.add(run)
        session.flush()

        new_out = AnalysisOutput(
            topic_id=topic_id,
            run_id=run.id,
            output_type="characters",
            title="New output",
            content_json="{}",
            source_chunk_ids="[]",
            evidence_quotes="[]",
        )
        session.add(new_out)
        session.commit()
        session.refresh(new_out)
        assert new_out.run_id == run.id

    client.delete(f"/api/topics/{topic_id}")


def test_real_migration_on_old_schema():
    """Simulate old SQLite analysis_output table without run_id, verify ALTER TABLE."""
    import tempfile
    from pathlib import Path

    from sqlalchemy import create_engine, text

    from db import _migrate_analysis_output_run_id

    tmp = tempfile.mktemp(suffix=".sqlite")
    try:
        eng = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})

        with eng.connect() as conn:
            conn.execute(text("""
                CREATE TABLE analysis_output (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    job_id TEXT,
                    output_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    source_chunk_ids TEXT NOT NULL DEFAULT '[]',
                    evidence_quotes TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
            conn.execute(text(
                "INSERT INTO analysis_output (id, topic_id, output_type, title, content_json) "
                "VALUES ('old-1', 'topic-x', 'overview', 'Old', '{\"k\":\"v\"}')"
            ))
            conn.commit()

            info = conn.execute(text("PRAGMA table_info(analysis_output)")).fetchall()
            assert "run_id" not in [r[1] for r in info]

        # Patch engine temporarily to run migration
        import db as dbmod

        orig = dbmod.engine
        dbmod.engine = eng
        try:
            _migrate_analysis_output_run_id()
        finally:
            dbmod.engine = orig

        with eng.connect() as conn:
            info = conn.execute(text("PRAGMA table_info(analysis_output)")).fetchall()
            assert "run_id" in [r[1] for r in info]

            row = conn.execute(
                text("SELECT id, run_id, content_json FROM analysis_output WHERE id='old-1'")
            ).fetchone()
            assert row is not None
            assert row[1] is None
            assert row[2] == '{"k":"v"}'
    finally:
        eng.dispose()
        try:
            Path(tmp).unlink()
        except OSError:
            pass
