"""Hybrid storage for large analysis JSON artifacts.

Content <= ARTIFACT_THRESHOLD_BYTES stays inline in SQLite.
Content > ARTIFACT_THRESHOLD_BYTES is written to disk under
data/topics/{topic_id}/artifacts/ and a pointer row is stored
in AnalysisArtifact.
"""

import hashlib
import json

from sqlmodel import Session, select

import config
from models.analysis_artifact import AnalysisArtifact

ARTIFACT_THRESHOLD_BYTES = 65536  # 64 KB


def _artifact_dir(topic_id: str, artifact_type: str) -> str:
    """Relative path: topics/{topic_id}/artifacts/{artifact_type}/"""
    return f"topics/{topic_id}/artifacts/{artifact_type}/"


def _ensure_artifact_dir(topic_id: str, artifact_type: str) -> str:
    abs_path = config.DATA_DIR.resolve() / _artifact_dir(topic_id, artifact_type)
    abs_path.mkdir(parents=True, exist_ok=True)
    return str(abs_path)


def _compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def write_json_artifact(
    topic_id: str,
    run_id: str | None,
    artifact_type: str,
    owner_table: str,
    owner_id: str,
    json_str: str,
) -> AnalysisArtifact:
    abs_dir = _ensure_artifact_dir(topic_id, artifact_type)
    filename = f"{owner_id}.json"
    abs_path = f"{abs_dir}/{filename}"

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    size = len(json_str.encode("utf-8"))
    sha = _compute_sha256(json_str)
    rel_path = f"{_artifact_dir(topic_id, artifact_type)}{filename}"

    return AnalysisArtifact(
        topic_id=topic_id,
        run_id=run_id,
        artifact_type=artifact_type,
        owner_table=owner_table,
        owner_id=owner_id,
        storage_path=rel_path,
        size_bytes=size,
        sha256=sha,
    )


def read_json_artifact(
    session: Session,
    owner_table: str,
    owner_id: str,
) -> str | None:
    """Read artifact JSON from disk. Returns None if not found or not an artifact."""
    row = session.exec(
        select(AnalysisArtifact).where(
            AnalysisArtifact.owner_table == owner_table,
            AnalysisArtifact.owner_id == owner_id,
        )
    ).first()
    if row is None:
        return None

    abs_path = config.DATA_DIR.resolve() / row.storage_path
    if not abs_path.exists():
        return None

    return abs_path.read_text(encoding="utf-8")


def delete_artifact(
    session: Session,
    owner_table: str,
    owner_id: str,
) -> bool:
    """Delete artifact row and file. Returns True if deleted."""
    row = session.exec(
        select(AnalysisArtifact).where(
            AnalysisArtifact.owner_table == owner_table,
            AnalysisArtifact.owner_id == owner_id,
        )
    ).first()
    if row is None:
        return False

    abs_path = config.DATA_DIR.resolve() / row.storage_path
    if abs_path.exists():
        abs_path.unlink()

    session.delete(row)
    return True


def delete_artifacts_for_topic(session: Session, topic_id: str) -> int:
    """Delete all artifact rows and files for a topic. Returns count."""
    rows = session.exec(select(AnalysisArtifact).where(AnalysisArtifact.topic_id == topic_id)).all()
    count = len(rows)
    for row in rows:
        abs_path = config.DATA_DIR.resolve() / row.storage_path
        if abs_path.exists():
            abs_path.unlink()
        session.delete(row)
    return count


def maybe_store_large_json(
    session: Session,
    topic_id: str,
    run_id: str | None,
    artifact_type: str,
    owner_table: str,
    owner_id: str,
    json_str: str,
) -> str:
    """Store large JSON as artifact, return empty string. Small JSON returns json_str unchanged."""
    size = len(json_str.encode("utf-8"))
    if size <= ARTIFACT_THRESHOLD_BYTES:
        return json_str

    artifact = write_json_artifact(
        topic_id=topic_id,
        run_id=run_id,
        artifact_type=artifact_type,
        owner_table=owner_table,
        owner_id=owner_id,
        json_str=json_str,
    )
    session.add(artifact)
    # Return a compact inline stub so consumers can still read content_json
    stub = json.dumps(
        {
            "_artifact": True,
            "owner_table": owner_table,
            "owner_id": owner_id,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
        },
        ensure_ascii=False,
    )
    return stub


def read_json_inline_or_artifact(
    session: Session,
    content_json: str,
    owner_table: str,
    owner_id: str,
) -> str:
    """If content_json is an artifact stub, read from disk. Otherwise return as-is."""
    try:
        stub = json.loads(content_json)
        if isinstance(stub, dict) and stub.get("_artifact"):
            artifact_data = read_json_artifact(session, owner_table, owner_id)
            if artifact_data is not None:
                return artifact_data
    except (json.JSONDecodeError, TypeError):
        pass
    return content_json
