"""Tests for v0.2 Step 12 — Artifact Storage Service."""

import json

from sqlmodel import Session

import config
from models.analysis_artifact import AnalysisArtifact
from services.artifact_storage_service import (
    ARTIFACT_THRESHOLD_BYTES,
    delete_artifact,
    delete_artifacts_for_topic,
    maybe_store_large_json,
    read_json_artifact,
    read_json_inline_or_artifact,
    write_json_artifact,
)


def _setup_topic(session):
    from models.model_provider import ModelProvider
    from models.topic import Topic

    prov = ModelProvider(
        name="Art P",
        provider_type="openai_compatible",
        base_url="http://mock",
        api_key="sk-m",
        model_name="m",
        is_default=True,
    )
    session.add(prov)
    session.flush()
    topic = Topic(name="Art Topic", provider_id=prov.id, status="parsed")
    session.add(topic)
    session.flush()
    return topic.id


def test_small_json_stays_inline(engine):
    """JSON under threshold should not be moved to artifact."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    small = json.dumps({"key": "value"})
    with Session(engine) as session:
        result = maybe_store_large_json(
            session,
            tid,
            None,
            "final_output",
            "analysis_output",
            "test-id-1",
            small,
        )
        assert "key" in result
        session.commit()

    with Session(engine) as session:
        rows = session.exec(
            __import__("sqlmodel").select(AnalysisArtifact).where(AnalysisArtifact.topic_id == tid)
        ).all()
        assert len(rows) == 0


def test_large_json_stored_as_artifact(engine):
    """JSON over threshold should be stored on disk with DB pointer."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    large = json.dumps({"data": "x" * ARTIFACT_THRESHOLD_BYTES})
    with Session(engine) as session:
        result = maybe_store_large_json(
            session,
            tid,
            None,
            "final_output",
            "analysis_output",
            "test-id-large",
            large,
        )
        stub = json.loads(result)
        assert stub.get("_artifact") is True
        session.commit()

    with Session(engine) as session:
        rows = session.exec(
            __import__("sqlmodel").select(AnalysisArtifact).where(AnalysisArtifact.topic_id == tid)
        ).all()
        assert len(rows) == 1
        assert rows[0].size_bytes > ARTIFACT_THRESHOLD_BYTES

        abs_path = config.DATA_DIR.resolve() / rows[0].storage_path
        assert abs_path.exists()
        content = abs_path.read_text(encoding="utf-8")
        assert "x" * ARTIFACT_THRESHOLD_BYTES in content


def test_write_and_read_artifact(engine):
    """Round-trip: write to artifact, read back."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    data = json.dumps({"characters": [{"name": "张三"}]}, ensure_ascii=False)
    with Session(engine) as session:
        artifact = write_json_artifact(
            tid,
            None,
            "final_output",
            "analysis_output",
            "test-id-2",
            data,
        )
        session.add(artifact)
        session.commit()

    with Session(engine) as session:
        result = read_json_artifact(session, "analysis_output", "test-id-2")
        assert result is not None
        assert "张三" in result


def test_read_json_inline_or_artifact_stub(engine):
    """read_json_inline_or_artifact resolves artifact stubs transparently."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    large = json.dumps({"data": "y" * ARTIFACT_THRESHOLD_BYTES})
    with Session(engine) as session:
        stub = maybe_store_large_json(
            session,
            tid,
            None,
            "final_output",
            "analysis_output",
            "test-stub-1",
            large,
        )
        session.commit()

    with Session(engine) as session:
        resolved = read_json_inline_or_artifact(
            session,
            stub,
            "analysis_output",
            "test-stub-1",
        )
        assert "y" * ARTIFACT_THRESHOLD_BYTES in resolved

    regular = json.dumps({"key": "value"})
    with Session(engine) as session:
        out = read_json_inline_or_artifact(
            session,
            regular,
            "analysis_output",
            "nonexistent",
        )
        assert out == regular


def test_delete_artifact(engine):
    """delete_artifact removes both DB row and disk file."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    data = json.dumps({"test": True})
    with Session(engine) as session:
        artifact = write_json_artifact(
            tid,
            None,
            "debug",
            "analysis_output",
            "test-del-1",
            data,
        )
        session.add(artifact)
        session.commit()
        abs_path = config.DATA_DIR.resolve() / artifact.storage_path
        assert abs_path.exists()

    with Session(engine) as session:
        deleted = delete_artifact(session, "analysis_output", "test-del-1")
        assert deleted is True
        session.commit()

    with Session(engine) as session:
        assert not abs_path.exists()
        rows = session.exec(
            __import__("sqlmodel").select(AnalysisArtifact).where(AnalysisArtifact.topic_id == tid)
        ).all()
        assert len(rows) == 0


def test_delete_artifacts_for_topic(engine):
    """delete_artifacts_for_topic removes all artifacts for a topic."""
    with Session(engine) as session:
        tid = _setup_topic(session)
        session.commit()

    paths = []
    with Session(engine) as session:
        for i in range(3):
            artifact = write_json_artifact(
                tid,
                None,
                "debug",
                "analysis_output",
                f"topic-del-{i}",
                json.dumps({"idx": i}),
            )
            session.add(artifact)
            paths.append(config.DATA_DIR.resolve() / artifact.storage_path)
        session.commit()

    for p in paths:
        assert p.exists()

    with Session(engine) as session:
        count = delete_artifacts_for_topic(session, tid)
        assert count == 3
        session.commit()

    for p in paths:
        assert not p.exists()

    with Session(engine) as session:
        rows = session.exec(
            __import__("sqlmodel").select(AnalysisArtifact).where(AnalysisArtifact.topic_id == tid)
        ).all()
        assert len(rows) == 0
