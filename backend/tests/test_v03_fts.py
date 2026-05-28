"""v0.3 Step 5 — FTS Index Service tests."""

import io
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from services.fts_service import (
    delete_topic_chunk_fts,
    rebuild_topic_chunk_fts,
    search_chunks,
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


# ── Review regression tests ──


class TestMultiWordFTSQuery:
    def test_non_adjacent_words_match(self, tmp_path):
        """Multi-word query matches chunks containing any token, not just contiguous phrase."""
        db_path = tmp_path / "multiword.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_fts,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="The quick brown fox jumps over the lazy dog.",
                start_char=0,
                end_char=44,
                char_count=44,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            # "quick fox" — words not adjacent in text but both present
            results = search_chunks_fts(tid, "quick fox", session)
            assert len(results) >= 1

            # "fox dog" — "dog" exists but "fox" and "dog" not adjacent
            results = search_chunks_fts(tid, "fox dog", session)
            assert len(results) >= 1


class TestEmptyRebuildCommit:
    def test_empty_rebuild_commits_delete(self, tmp_path):
        """After rebuild with 0 chunks, new session sees empty FTS."""
        db_path = tmp_path / "empty_rebuild.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_fts,
        )

        tid = str(uuid4())
        did = str(uuid4())

        # Insert a chunk, build FTS, then delete the chunk
        with Session(engine) as s1:
            ensure_chunk_fts_table(s1)
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="Hello world.",
                start_char=0,
                end_char=12,
                char_count=12,
            )
            s1.add(c)
            s1.commit()
            rebuild_topic_chunk_fts(tid, s1)

        # Verify FTS has data
        with Session(engine) as s2:
            assert len(search_chunks_fts(tid, "Hello", s2)) == 1

        # Delete chunk and rebuild with 0 chunks
        with Session(engine) as s3:
            chunk = s3.exec(select(Chunk).where(Chunk.topic_id == tid)).first()
            s3.delete(chunk)
            s3.commit()
            rebuild_topic_chunk_fts(tid, s3)

        # New session should see empty FTS
        with Session(engine) as s4:
            assert len(search_chunks_fts(tid, "Hello", s4)) == 0


class TestUnifiedSearch:
    def test_cjk_fallback_used(self, tmp_path):
        db_path = tmp_path / "unified_cjk.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table, rebuild_topic_chunk_fts

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

            results = search_chunks(tid, "中文测试", session)
            assert len(results) >= 1
            assert any("中文测试" in r["snippet"] for r in results)

    def test_english_fts_used(self, tmp_path):
        db_path = tmp_path / "unified_en.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table, rebuild_topic_chunk_fts

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="The quick brown fox.",
                start_char=0,
                end_char=20,
                char_count=20,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "quick", session)
            assert len(results) >= 1
            assert results[0]["method"] == "fts"

    def test_dedup_removes_duplicates(self, tmp_path):
        """When both FTS and fallback hit the same chunk, dedup by chunk_id."""
        db_path = tmp_path / "unified_dedup.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import ensure_chunk_fts_table, rebuild_topic_chunk_fts

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="这是一个测试中文内容。",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "测试", session)
            chunk_ids = [r["chunk_id"] for r in results]
            assert len(chunk_ids) == len(set(chunk_ids))  # no duplicates


class TestPunctuationInQuery:
    def test_question_mark_in_query(self, tmp_path):
        """Query 'who? quick' should find 'Who is quick?' via token extraction."""
        db_path = tmp_path / "punct_qmark.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="Who is quick? The quick fox is here.",
                start_char=0,
                end_char=35,
                char_count=35,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "who? quick", session)
            assert len(results) >= 1

    def test_hyphen_in_query(self, tmp_path):
        """Query 'quick-fox' should find 'quick fox' via token extraction."""
        db_path = tmp_path / "punct_hyphen.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="The quick brown fox.",
                start_char=0,
                end_char=20,
                char_count=20,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "quick-fox", session)
            assert len(results) >= 1


class TestExplicitOR:
    def test_or_matches_across_different_chunks(self, tmp_path):
        """Query 'quick dog' with OR should match chunks containing either word."""
        db_path = tmp_path / "or_chunks.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_fts,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c1 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="The quick brown fox.",
                start_char=0,
                end_char=20,
                char_count=20,
            )
            c2 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=1,
                chapter_index=0,
                text="The lazy dog sleeps.",
                start_char=21,
                end_char=41,
                char_count=20,
            )
            session.add_all([c1, c2])
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_fts(tid, "quick dog", session)
            # Should match both chunks via OR (at least 2)
            assert len(results) >= 2

    def test_and_would_fail_but_or_passes(self, tmp_path):
        """quick is in chunk 0, dog is in chunk 1; AND would return 0, OR returns both."""
        db_path = tmp_path / "or_vs_and.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_fts,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c1 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="quick",
                start_char=0,
                end_char=5,
                char_count=5,
            )
            c2 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=1,
                chapter_index=0,
                text="dog",
                start_char=6,
                end_char=9,
                char_count=3,
            )
            session.add_all([c1, c2])
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            # OR query
            results = search_chunks_fts(tid, "quick dog", session)
            assert len(results) == 2  # both chunks returned

            # Single-word queries still work
            assert len(search_chunks_fts(tid, "quick", session)) == 1
            assert len(search_chunks_fts(tid, "dog", session)) == 1


class TestFTSReservedWords:
    def test_or_keyword_in_query(self, tmp_path):
        """Query 'hello OR' should find chunk containing 'hello', not crash."""
        db_path = tmp_path / "reserved_or.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="hello world",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "hello OR", session)
            assert len(results) >= 1
            assert any("hello" in r["snippet"].lower() for r in results)

    def test_and_not_keywords_in_query(self, tmp_path):
        """Query 'to be AND not' should find matching chunks."""
        db_path = tmp_path / "reserved_and.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="to be or not to be",
                start_char=0,
                end_char=18,
                char_count=18,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "to be AND not", session)
            assert len(results) >= 1


class TestCJKPunctuationFallback:
    def test_cjk_with_punctuation(self, tmp_path):
        """Query '刘备？曹操' should find '刘备和曹操相遇' via cleaned fallback."""
        db_path = tmp_path / "cjk_punct.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="刘备和曹操相遇于赤壁。",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "刘备？曹操", session)
            assert len(results) >= 1


class TestLIKEWildcardEscape:
    def test_underscore_in_query(self, tmp_path):
        """Query '_' should not match every chunk via LIKE wildcard."""
        db_path = tmp_path / "like_underscore.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_keyword_fallback,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            for i, text in enumerate(["alpha", "beta", "gamma"]):
                c = Chunk(
                    topic_id=tid,
                    document_id=did,
                    chunk_index=i,
                    chapter_index=0,
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    char_count=len(text),
                )
                session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            # Query with underscore should match only chunks literally containing '_'
            results = search_chunks_keyword_fallback(tid, "_", session)
            # None of our test chunks contain literal underscore
            assert len(results) == 0

    def test_percent_in_query(self, tmp_path):
        """Query '%' should not match every chunk via LIKE wildcard."""
        db_path = tmp_path / "like_percent.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_keyword_fallback,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="hello world",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_keyword_fallback(tid, "%", session)
            assert len(results) == 0


class TestCJKCharOverlap:
    def test_unsegmented_cjk_query(self, tmp_path):
        """Query '刘备曹操' (no spaces) should find '刘备和曹操相遇' via char overlap."""
        db_path = tmp_path / "cjk_overlap.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="刘备和曹操相遇于赤壁。",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks(tid, "刘备曹操", session)
            assert len(results) >= 1

    def test_common_char_no_false_match(self, tmp_path):
        """Query '不存在' should NOT match text that only shares stop char '在'."""
        db_path = tmp_path / "cjk_nofalse.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_keyword_fallback,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="他是在那里了。",
                start_char=0,
                end_char=7,
                char_count=7,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_keyword_fallback(tid, "不存在", session)
            # '不存在' → non-stop chars after filtering: only '存'
            # (不 and 在 are stop words). With only 1 non-stop char,
            # no AND group is created, so only full-token LIKE '%不存在%'
            # runs — which does NOT match '他是在那里了。'
            assert len(results) == 0

    def test_all_stop_chars_falls_back_to_full_token_only(self, tmp_path):
        """Query '这是他' (all stop chars) only uses full-token LIKE, no AND group."""
        db_path = tmp_path / "cjk_allstop.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_keyword_fallback,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c1 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="这是他说的那句话。",
                start_char=0,
                end_char=9,
                char_count=9,
            )
            c2 = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=1,
                chapter_index=0,
                text="他是在那里了。",
                start_char=10,
                end_char=17,
                char_count=7,
            )
            session.add_all([c1, c2])
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_keyword_fallback(tid, "这是他", session)
            # Only c1 contains '这是他' as a literal substring
            assert len(results) == 1
            assert "这是他" in results[0]["snippet"]

    def test_duplicate_non_stop_char_does_not_degenerate_to_single(self, tmp_path):
        """Query '刘刘' (duplicate non-stop char) should NOT match text with just one '刘'."""
        db_path = tmp_path / "cjk_dup.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_keyword_fallback,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="刘备和曹操相遇于赤壁。",
                start_char=0,
                end_char=11,
                char_count=11,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_keyword_fallback(tid, "刘刘", session)
            # After dedup: non_stop = ['刘'], len=1 → no AND group.
            # Full-token LIKE '%刘刘%' won't match '刘备和曹操相遇于赤壁。'
            assert len(results) == 0


class TestScorePrecision:
    def test_score_has_two_decimal_places(self, tmp_path):
        db_path = tmp_path / "score_prec.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        import models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from models.chunk import Chunk
        from services.fts_service import (
            ensure_chunk_fts_table,
            rebuild_topic_chunk_fts,
            search_chunks_fts,
        )

        with Session(engine) as session:
            ensure_chunk_fts_table(session)
            tid, did = str(uuid4()), str(uuid4())
            c = Chunk(
                topic_id=tid,
                document_id=did,
                chunk_index=0,
                chapter_index=0,
                text="apple apple apple banana.",
                start_char=0,
                end_char=26,
                char_count=26,
            )
            session.add(c)
            session.commit()
            rebuild_topic_chunk_fts(tid, session)

            results = search_chunks_fts(tid, "apple", session)
            assert len(results) >= 1
            score = results[0]["score"]
            # Score should be a float, not rounded to 0
            assert isinstance(score, (int, float))
