"""v0.3 Step 9 — Entity Evidence + Similar Scenes API tests."""

import io
import json

from fastapi.testclient import TestClient


def _create_topic(client: TestClient, name: str = "Entity Test") -> str:
    resp = client.post("/api/topics", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_and_parse(client: TestClient, topic_id: str, text: str) -> None:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", io.BytesIO(text.encode("utf-8")))},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(f"/api/topics/{topic_id}/parse")
    assert resp.status_code == 200, resp.text


def _create_atoms(session, topic_id: str, run_id: str, atoms_data: list[dict]) -> list[str]:
    """Create ExtractedAtom rows and return their IDs."""
    from models.extracted_atom import ExtractedAtom

    ids = []
    for ad in atoms_data:
        atom = ExtractedAtom(
            topic_id=topic_id,
            run_id=run_id,
            atom_type=ad.get("atom_type", "character"),
            stable_id=ad["stable_id"],
            canonical_name=ad.get("canonical_name", ""),
            title=ad.get("title", ""),
            content_json=ad.get("content_json", "{}"),
            source_chunk_ids=json.dumps(ad.get("source_chunk_ids", [])),
            evidence_quotes=json.dumps(ad.get("evidence_quotes", [])),
            confidence=ad.get("confidence", 0.9),
            chunk_id=ad.get("chunk_id"),
        )
        session.add(atom)
        session.flush()
        ids.append(atom.id)
    session.commit()
    return ids


def _create_minimal_run(session, topic_id: str) -> str:
    from models.analysis_run import AnalysisRun

    run = AnalysisRun(topic_id=topic_id)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run.id


# ── Entity Evidence ──


class TestEntityEvidence:
    def test_entity_found_by_stable_id(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n刘备和关羽在桃园结义。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        # Get a chunk to reference
        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        chunk = chunks[0]

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_liubei",
                    "canonical_name": "刘备",
                    "title": "刘玄德",
                    "source_chunk_ids": [chunk.id],
                    "evidence_quotes": ["刘备出场。"],
                    "content_json": json.dumps({"aliases": ["玄德"]}),
                    "confidence": 0.95,
                }
            ],
        )

        resp = client.get(f"/api/topics/{topic_id}/entities/char_liubei/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "char_liubei"
        assert data["canonical_name"] == "刘备"
        assert len(data["atoms"]) >= 1
        assert data["atoms"][0]["stable_id"] == "char_liubei"
        assert data["atoms"][0]["confidence"] == 0.95
        # Evidence quotes parsed
        assert isinstance(data["atoms"][0]["evidence_quotes"], list)
        assert "刘备出场。" in data["atoms"][0]["evidence_quotes"]

    def test_entity_found_by_canonical_name(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n曹操率军南下。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        chunk = chunks[0]

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_caocao",
                    "canonical_name": "曹操",
                    "title": "曹孟德",
                    "source_chunk_ids": [chunk.id],
                    "evidence_quotes": ["曹操率军南下。"],
                    "confidence": 0.9,
                }
            ],
        )

        # Search using canonical_name
        resp = client.get(f"/api/topics/{topic_id}/entities/曹操/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["atoms"]) >= 1

    def test_source_chunks_resolved(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n诸葛亮出场。\n第二章\n\n诸葛亮北伐。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(
            sql_select(Chunk).where(Chunk.topic_id == topic_id).order_by(Chunk.chunk_index).limit(2)
        ).all()
        assert len(chunks) >= 2

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_zhugeliang",
                    "canonical_name": "诸葛亮",
                    "title": "诸葛孔明",
                    "source_chunk_ids": [chunks[0].id, chunks[1].id],
                    "evidence_quotes": ["诸葛亮出场。", "诸葛亮北伐。"],
                    "confidence": 0.9,
                }
            ],
        )

        resp = client.get(f"/api/topics/{topic_id}/entities/char_zhugeliang/evidence")
        assert resp.status_code == 200
        data = resp.json()
        # Chunks from source_chunk_ids should be loaded
        assert len(data["chunks"]) >= 2
        chunk_ids = {c["id"] for c in data["chunks"]}
        assert chunks[0].id in chunk_ids
        assert chunks[1].id in chunk_ids
        # Chunks should have excerpt (not full text)
        for c in data["chunks"]:
            assert len(c["excerpt"]) <= 300

    def test_related_outputs_returned(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n刘备与关羽张飞在桃园结义。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.analysis_output import AnalysisOutput
        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        chunk = chunks[0]

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_liubei",
                    "canonical_name": "刘备",
                    "source_chunk_ids": [chunk.id],
                    "evidence_quotes": ["桃园结义。"],
                    "confidence": 0.9,
                }
            ],
        )

        # Create an output that shares a chunk with the atom
        output = AnalysisOutput(
            topic_id=topic_id,
            output_type="characters",
            title="刘备分析",
            content_json=json.dumps({"name": "刘备", "description": "刘备是主角"}),
            source_chunk_ids=json.dumps([chunk.id]),
            evidence_quotes=json.dumps(["桃园结义。"]),
            confidence=0.9,
        )
        session.add(output)
        session.commit()

        resp = client.get(f"/api/topics/{topic_id}/entities/char_liubei/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["outputs"]) >= 1
        assert any(o["title"] == "刘备分析" for o in data["outputs"])

    def test_entity_not_found_returns_empty(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\nHello world.\n")

        resp = client.get(f"/api/topics/{topic_id}/entities/nonexistent_entity/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["atoms"] == []
        assert data["chunks"] == []
        assert data["outputs"] == []

    def test_topic_not_found(self, client):
        resp = client.get("/api/topics/nonexistent-id/entities/some_entity/evidence")
        assert resp.status_code == 404

    def test_limit_respected(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(
            client, topic_id, "第一章\n\n刘备出场。\n第二章\n\n关羽出场。\n第三章\n\n张飞出场。\n"
        )

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(3)).all()

        run_id = _create_minimal_run(session, topic_id)
        for i, ch in enumerate(chunks):
            _create_atoms(
                session,
                topic_id,
                run_id,
                [
                    {
                        "atom_type": "character",
                        "stable_id": "char_test",
                        "canonical_name": f"角色{i}",
                        "source_chunk_ids": [ch.id],
                        "evidence_quotes": [],
                        "confidence": 0.9,
                    }
                ],
            )

        resp = client.get(f"/api/topics/{topic_id}/entities/char_test/evidence?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["atoms"]) <= 2

    def test_lookup_by_atom_id(self, client):
        """Entity lookup should work with the atom's actual id."""
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n刘备出场。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        chunk = chunks[0]

        run_id = _create_minimal_run(session, topic_id)
        atom_ids = _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_liubei",
                    "canonical_name": "刘备",
                    "source_chunk_ids": [chunk.id],
                    "evidence_quotes": ["刘备出场。"],
                    "confidence": 0.9,
                }
            ],
        )

        # Lookup using the atom's UUID id
        resp = client.get(f"/api/topics/{topic_id}/entities/{atom_ids[0]}/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["atoms"]) >= 1
        assert data["atoms"][0]["id"] == atom_ids[0]

    def test_cross_topic_chunks_not_leaked(self, client):
        """Chunks from other topics must not appear in entity evidence."""
        topic_a = _create_topic(client, "Topic A")
        _upload_and_parse(client, topic_a, "第一章\n\nTopic A content.\n")

        topic_b = _create_topic(client, "Topic B")
        _upload_and_parse(client, topic_b, "第一章\n\nTopic B content.\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks_a = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_a).limit(1)).all()
        chunks_b = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_b).limit(1)).all()
        assert chunks_a and chunks_b

        run_id = _create_minimal_run(session, topic_a)
        _create_atoms(
            session,
            topic_a,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_test",
                    "canonical_name": "Test",
                    "source_chunk_ids": [chunks_b[0].id, chunks_a[0].id],
                    "evidence_quotes": ["test"],
                    "confidence": 0.9,
                }
            ],
        )

        resp = client.get(f"/api/topics/{topic_a}/entities/char_test/evidence")
        assert resp.status_code == 200
        data = resp.json()
        chunk_ids = {c["id"] for c in data["chunks"]}
        assert chunks_b[0].id not in chunk_ids, "Cross-topic chunk must not leak"
        assert chunks_a[0].id in chunk_ids

    def test_chunks_capped_by_limit(self, client):
        """Chunks should not exceed the limit, even if atoms reference many."""
        topic_id = _create_topic(client)
        _upload_and_parse(
            client,
            topic_id,
            "第一章\n\nA.\n第二章\n\nB.\n第三章\n\nC.\n第四章\n\nD.\n第五章\n\nE.\n",
        )

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(
            sql_select(Chunk).where(Chunk.topic_id == topic_id).order_by(Chunk.chunk_index).limit(5)
        ).all()
        assert len(chunks) >= 3

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_multi",
                    "canonical_name": "Multi",
                    "source_chunk_ids": [c.id for c in chunks],
                    "evidence_quotes": [],
                    "confidence": 0.9,
                }
            ],
        )

        resp = client.get(f"/api/topics/{topic_id}/entities/char_multi/evidence?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chunks"]) <= 2, f"Expected chunks <= 2, got {len(data['chunks'])}"


# ── Similar Scenes ──


class TestSimilarScenes:
    def test_by_query(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(
            client, topic_id, "第一章\n\n刘备与关羽张飞在桃园结义。\n第二章\n\n曹操率军南下。\n"
        )

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"query": "刘备", "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        for r in data["results"]:
            assert "chunk_id" in r
            assert "snippet" in r
            assert "score" in r

    def test_by_chunk_id(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(
            client,
            topic_id,
            "第一章\n\n刘备与关羽张飞在桃园结义。\n第二章\n\n曹操率军南下，欲取江南。\n",
        )

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(
            sql_select(Chunk).where(Chunk.topic_id == topic_id).order_by(Chunk.chunk_index).limit(2)
        ).all()
        assert len(chunks) >= 2
        seed_chunk = chunks[0]

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"chunk_id": seed_chunk.id, "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return other chunks but NOT the seed itself
        chunk_ids = [r["chunk_id"] for r in data["results"]]
        assert seed_chunk.id not in chunk_ids, "Seed chunk must not be in results"

    def test_by_chunk_id_excludes_self(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\n刘备与关羽张飞在桃园结义。\n")

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        assert len(chunks) == 1
        seed = chunks[0]

        # Only one chunk exists — similar scenes should return empty
        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"chunk_id": seed.id, "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert seed.id not in [r["chunk_id"] for r in data["results"]]

    def test_missing_params_422(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "第一章\n\nHello world.\n")

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
        )
        assert resp.status_code == 422

    def test_chunk_not_found_404(self, client):
        topic_id = _create_topic(client)

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"chunk_id": "nonexistent-chunk"},
        )
        assert resp.status_code == 404

    def test_topic_not_found(self, client):
        resp = client.get(
            "/api/topics/nonexistent-id/similar-scenes",
            params={"query": "hello"},
        )
        assert resp.status_code == 404

    def test_limit_respected(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(
            client, topic_id, "第一章\n\n刘备出场。\n第二章\n\n关羽出场。\n第三章\n\n张飞出场。\n"
        )

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"query": "出场", "limit": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_by_chunk_id_with_atoms(self, client):
        """chunk_id mode should incorporate atom names into search query."""
        topic_id = _create_topic(client)
        _upload_and_parse(
            client, topic_id, "第一章\n\n曹操和刘备在许昌会面。\n第二章\n\n曹操率军南下。\n"
        )

        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        chunks = session.exec(
            sql_select(Chunk).where(Chunk.topic_id == topic_id).order_by(Chunk.chunk_index).limit(2)
        ).all()
        assert len(chunks) >= 2

        run_id = _create_minimal_run(session, topic_id)
        _create_atoms(
            session,
            topic_id,
            run_id,
            [
                {
                    "atom_type": "character",
                    "stable_id": "char_caocao",
                    "canonical_name": "曹操",
                    "title": "曹孟德",
                    "chunk_id": chunks[0].id,
                    "source_chunk_ids": [chunks[0].id],
                    "evidence_quotes": ["曹操在许昌"],
                    "confidence": 0.9,
                }
            ],
        )

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"chunk_id": chunks[0].id, "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should find the other chunk (曹操率军南下) via atom seed
        assert len(data["results"]) >= 1
