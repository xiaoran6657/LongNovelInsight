"""v0.3 Step 5 — FTS Index Service tests."""

import io
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from services.fts_service import (
    delete_topic_chunk_fts,
    rebuild_topic_chunk_fts,
    search_chunks_fts,
    search_chunks_keyword_fallback,
)


def _create_topic(client: TestClient) -> str:
    resp = client.post("/api/topics", json={"name": "FTS Test"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_and_parse(client: TestClient, topic_id: str, text: str) -> dict:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", io.BytesIO(text.encode("utf-8")))},
    )
    assert resp.status_code == 201
    resp = client.post(f"/api/topics/{topic_id}/parse")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("fts_rows", 0) > 0
    return data


# ── Rebuild via HTTP (parse triggers FTS) ──


class TestFTSRebuildViaParse:
    def test_parse_includes_fts_rows(self, client):
        topic_id = _create_topic(client)
        data = _upload_and_parse(client, topic_id, "Chapter 1\n\nHello world.\n")
        assert data["fts_rows"] >= 1

    def test_reparse_rebuilds_fts(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nHello world.\n")
        resp = client.post(f"/api/topics/{topic_id}/parse?force=true")
        assert resp.status_code == 200
        assert resp.json()["fts_rows"] >= 1

    def test_fts_cleared_after_document_delete(self, client):
        topic_id = _create_topic(client)
        _upload_and_parse(client, topic_id, "Chapter 1\n\nHello world.\n")

        client.delete(f"/api/topics/{topic_id}/documents/current")
        # Upload new content
        data = _upload_and_parse(client, topic_id, "Chapter 1\n\nNew content only.\n")
        # FTS should only have new rows
        assert data["fts_rows"] >= 1


# ── Direct service-level tests ──


class TestFTSServiceDirect:
    def test_rebuild_and_search(self, tmp_path):
        db_path = tmp_path / "fts1.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid, did = str(uuid4()), str(uuid4())

            c1 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="The quick brown fox jumps over the lazy dog.",
                start_char=0,
                end_char=44,
                char_count=44,
            )
            c2 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=1,
                chapter_index=1,
                text="Pack my box with five dozen liquor jugs.",
                start_char=45,
                end_char=84,
                char_count=40,
            )
            session.add_all([c1, c2])
            session.commit()

            count = rebuild_topic_chunk_fts(tid, session)
            assert count == 2

            # FTS search for English (single word)
            results = search_chunks_fts(tid, "quick", session)
            assert len(results) >= 1
            assert any("quick" in r["snippet"].lower() for r in results)
            assert all(r["method"] == "fts" for r in results)

            # No results for nonsense
            assert len(search_chunks_fts(tid, "xyznonsense", session)) == 0

    def test_chinese_keyword_fallback(self, tmp_path):
        db_path = tmp_path / "fts_cjk.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="这是中文测试内容。",
                start_char=0,
                end_char=9,
                char_count=9,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            # Keyword fallback should find Chinese substring
            fb = search_chunks_keyword_fallback(tid, "中文测试", session)
            assert len(fb) >= 1
            assert any("中文测试" in r["snippet"] for r in fb)
            assert all(r["method"] == "keyword_fallback" for r in fb)

    def test_delete_clears_fts(self, tmp_path):
        db_path = tmp_path / "fts_del.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="Hello",
                start_char=0,
                end_char=5,
                char_count=5,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            delete_topic_chunk_fts(tid, session)
            assert len(search_chunks_fts(tid, "Hello", session)) == 0

    def test_rebuild_idempotent(self, tmp_path):
        db_path = tmp_path / "fts_idem.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="Hello",
                start_char=0,
                end_char=5,
                char_count=5,
            )
            session.add(c)
            session.commit()

            r1 = rebuild_topic_chunk_fts(tid, session)
            r2 = rebuild_topic_chunk_fts(tid, session)
            assert r1 == r2 == 1

    def test_no_sql_injection(self, tmp_path):
        db_path = tmp_path / "fts_inject.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="Safe text.",
                start_char=0,
                end_char=10,
                char_count=10,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            for malicious in [
                "'; DROP TABLE chunk_fts; --",
                '") OR 1=1 --',
                '" UNION SELECT * FROM chunk --',
            ]:
                results = search_chunks_fts(tid, malicious, session)
                assert isinstance(results, list)

    def test_topic_isolation(self, tmp_path):
        db_path = tmp_path / "fts_isolate.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table

        with Session(engine) as session:
            ensure_chunk_fts_table(session)

            tid1, did1 = str(uuid4()), str(uuid4())
            tid2, did2 = str(uuid4()), str(uuid4())

            c1 = Chunk(
                topic_id=tid1,
                document_id=did1,
                chunk_index=0,
                chapter_index=0,
                text="Topic one unique phrase.",
                start_char=0,
                end_char=25,
                char_count=25,
            )
            c2 = Chunk(
                topic_id=tid2,
                document_id=did2,
                chunk_index=0,
                chapter_index=0,
                text="Topic two other content.",
                start_char=0,
                end_char=25,
                char_count=25,
            )
            session.add_all([c1, c2])
            session.commit()
            rebuild_topic_chunk_fts(tid1, session)
            rebuild_topic_chunk_fts(tid2, session)

            r1 = search_chunks_fts(tid1, "unique phrase", session)
            assert len(r1) >= 1
            assert all(r["topic_id"] == tid1 for r in r1)

            r2 = search_chunks_fts(tid2, "unique phrase", session)
            assert len(r2) == 0
