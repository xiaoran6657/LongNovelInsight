"""v0.3 end-to-end smoke tests — TestClient, no live server needed.

Covers the full v0.3 flow: TXT upload/parse/search/retrieve/chat/cleanup,
EPUB upload/parse/metadata/chapter order/locator, entity evidence,
similar scenes, and FTS/retrieval benchmarks.

Run:
    pytest tests/integration/test_v03_smoke.py -v -s -m integration
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from unittest.mock import patch

import pytest

TXT_SAMPLE = (
    "第一章 长安初遇\n\n"
    "长安城的秋日格外清爽，街道两旁的梧桐叶泛着金黄。\n\n"
    "张三背着行囊，踏入了这座传说中的都城。他在城门口站了许久，"
    "望着熙熙攘攘的人群和巍峨的城墙，心中涌起难以言说的激动。\n\n"
    "第二章 东市寻人\n\n"
    "街边的小贩吆喝着，卖糖葫芦的老汉推着车从人群中穿过。"
    "张三摸了摸怀中的书信，那是师父临终前交给他的。\n\n"
    "第三章 桂花小院\n\n"
    "李四是个四十来岁的中年人，面容清癯，眼神却格外锐利。"
    "他看了信后，沉默良久，最后对张三说：你师父是我的救命恩人。\n\n"
    "第四章 修行之始\n\n"
    "从此，张三便在李四家中住了下来，开始了他在长安城的修行生涯。"
    "每日清晨，李四都会在院中练剑，剑光如雪，张三看得心驰神往。"
)

CHAT_MOCK_PATH = "services.chat_service.OpenAICompatibleLLMClient.chat"

TXT_FILENAME = "smoke_test.txt"
EPUB_FILENAME = "smoke_test.epub"


def _mock_chat_response(*args, **kwargs):
    from services.llm_client import LLMResponse

    return LLMResponse(
        content=json.dumps(
            {
                "answer": "张三是一个修行者，他在长安城遇到了李四。",
                "evidence": ["张三背着行囊，踏入了这座传说中的都城。"],
                "uncertainty": None,
            }
        ),
        model="test",
        usage={},
    )


def _build_minimal_epub_bytes(title: str, author: str, chapters: list[tuple[str, str]]) -> bytes:
    """Build an in-memory EPUB with the given chapters (title, content)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")

        container_xml = (
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles>"
            "</container>"
        )
        zf.writestr("META-INF/container.xml", container_xml)

        manifest_items = []
        spine_items = []
        for i, (ch_title, ch_text) in enumerate(chapters):
            href = f"chapter{i + 1}.xhtml"
            mid = f"ch{i + 1}"
            manifest_items.append(
                f'<item id="{mid}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{mid}"/>')
            xhtml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<!DOCTYPE html>"
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>{ch_title}</title></head>"
                f"<body><h1>{ch_title}</h1><p>{ch_text}</p></body>"
                "</html>"
            )
            zf.writestr(href, xhtml)

        opf = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package version="2.0" unique-identifier="uid"'
            ' xmlns="http://www.idpf.org/2007/opf"'
            ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<metadata>"
            f"<dc:title>{title}</dc:title>"
            f"<dc:creator>{author}</dc:creator>"
            "<dc:language>zh-CN</dc:language>"
            '<dc:identifier id="uid">urn:uuid:smoke-test-epub</dc:identifier>'
            "</metadata>"
            f"<manifest>{''.join(manifest_items)}</manifest>"
            f"<spine>{''.join(spine_items)}</spine>"
            "</package>"
        )
        zf.writestr("content.opf", opf)
    return buf.getvalue()


# ── TXT Smoke Test ──


@pytest.mark.integration
class TestV03TxtSmoke:
    def test_full_txt_flow(self, client):
        """Full v0.3 TXT flow: create → upload → parse → search → retrieve →
        chat → entity evidence → similar scenes → cleanup."""
        # --- Provider ---
        resp = client.post(
            "/api/providers",
            json={
                "name": "smoke-txt-provider",
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com",
                "api_key": "sk-smoke",
                "model_name": "test-model",
                "is_default": True,
            },
        )
        assert resp.status_code == 201

        # --- Topic ---
        resp = client.post("/api/topics", json={"name": "v0.3 TXT Smoke"})
        assert resp.status_code == 201
        topic_id = resp.json()["id"]

        # --- Upload TXT ---
        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": (TXT_FILENAME, io.BytesIO(TXT_SAMPLE.encode("utf-8")))},
        )
        assert resp.status_code == 201

        # --- Parse ---
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

        # --- Chapters ---
        resp = client.get(f"/api/topics/{topic_id}/chapters")
        assert resp.status_code == 200
        chapters = resp.json()["chapters"]
        assert len(chapters) >= 1

        # --- Chunks ---
        resp = client.get(f"/api/topics/{topic_id}/chunks")
        assert resp.status_code == 200
        chunks = resp.json()["chunks"]
        assert len(chunks) >= 1

        # --- Document metadata ---
        resp = client.get(f"/api/topics/{topic_id}/documents/current/metadata")
        assert resp.status_code == 200
        meta = resp.json()
        assert meta["file_type"] == "txt"

        # --- Search (CJK) ---
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "张三", "limit": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any("张三" in r.get("snippet", "") for r in results)

        # --- Search (English-like) ---
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "chapter", "limit": 5},
        )
        assert resp.status_code == 200

        # --- Retrieve ---
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "张三 修行", "top_k": 5, "persist_trace": True},
        )
        assert resp.status_code == 200
        ret_data = resp.json()
        assert len(ret_data["results"]) >= 1
        assert ret_data["trace_id"] is not None
        assert ret_data["warning"] is None

        # --- Chat (mocked) ---
        resp = client.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "Smoke Chat"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        with patch(CHAT_MOCK_PATH, side_effect=_mock_chat_response):
            resp = client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "张三是谁？"},
            )
            assert resp.status_code == 200
            chat_data = resp.json()
            assert chat_data["role"] == "assistant"
            assert len(chat_data.get("content", "")) > 0
            evidence = chat_data.get("evidence_json")
            assert isinstance(evidence, list)

        # --- Similar scenes ---
        chunk_id = chunks[0]["id"]
        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"chunk_id": chunk_id, "limit": 5},
        )
        assert resp.status_code == 200
        sim = resp.json()["results"]
        assert chunk_id not in [r["chunk_id"] for r in sim]

        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"query": "长安", "limit": 3},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

        # --- Cleanup ---
        resp = client.delete(f"/api/topics/{topic_id}")
        assert resp.status_code == 200

        # Find and delete the provider
        resp = client.get("/api/providers")
        for p in resp.json().get("providers", []):
            if p["name"] == "smoke-txt-provider":
                client.delete(f"/api/providers/{p['id']}")


# ── EPUB Smoke Test ──


@pytest.mark.integration
class TestV03EpubSmoke:
    def test_full_epub_flow(self, client):
        """Full v0.3 EPUB flow: create → upload → parse → metadata →
        chapter order → locator → search → retrieve → cleanup."""
        # --- Provider ---
        resp = client.post(
            "/api/providers",
            json={
                "name": "smoke-epub-provider",
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com",
                "api_key": "sk-smoke",
                "model_name": "test-model",
                "is_default": True,
            },
        )
        assert resp.status_code == 201

        # --- Topic ---
        resp = client.post("/api/topics", json={"name": "v0.3 EPUB Smoke"})
        assert resp.status_code == 201
        topic_id = resp.json()["id"]

        # --- Upload EPUB ---
        epub_bytes = _build_minimal_epub_bytes(
            "长风录",
            "李青",
            [
                ("第一章 少年游", "少年李明出生在江南的一个小镇。他从小就梦想着仗剑走天涯。"),
                ("第二章 江湖险", "李明离开了家乡，踏入了传说中的江湖。他遇到了形形色色的人物。"),
                ("第三章 风雨夜", "那一夜风雨交加，李明在破庙中遇到了一位神秘的老者。"),
            ],
        )
        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": (EPUB_FILENAME, io.BytesIO(epub_bytes))},
        )
        assert resp.status_code == 201

        # --- Parse EPUB ---
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

        # --- Metadata ---
        resp = client.get(f"/api/topics/{topic_id}/documents/current/metadata")
        assert resp.status_code == 200
        meta = resp.json()
        assert meta["file_type"] == "epub"
        assert meta["metadata"]["source_format"] == "epub"

        # --- Chapters (spine order) ---
        resp = client.get(f"/api/topics/{topic_id}/chapters")
        assert resp.status_code == 200
        chapters = resp.json()["chapters"]
        assert len(chapters) >= 3
        titles = [ch["title"] for ch in chapters]
        assert any("少年游" in t for t in titles)

        # --- Chunks ---
        resp = client.get(f"/api/topics/{topic_id}/chunks")
        assert resp.status_code == 200
        chunks = resp.json()["chunks"]
        assert len(chunks) >= 1

        # --- Locator ---
        chunk_id = chunks[0]["id"]
        resp = client.get(f"/api/topics/{topic_id}/chunks/{chunk_id}/locator")
        assert resp.status_code == 200
        loc = resp.json()
        assert loc["chunk_id"] == chunk_id
        assert len(loc["excerpt"]) > 0

        # --- EPUB search ---
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "李明", "limit": 5},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

        # --- Retrieve ---
        resp = client.post(
            f"/api/topics/{topic_id}/retrieve",
            json={"query": "江湖", "top_k": 5},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

        # --- Chat (mocked) ---
        resp = client.post(
            f"/api/topics/{topic_id}/chat/sessions",
            json={"title": "EPUB Chat"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        with patch(CHAT_MOCK_PATH, side_effect=_mock_chat_response):
            resp = client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"content": "李明是谁？"},
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == "assistant"

        # --- Entity evidence for EPUB ---
        # Create an atom manually to test entity lookup
        from db import get_session
        from main import app

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        from sqlmodel import select as sql_select

        from models.chunk import Chunk

        db_chunks = session.exec(sql_select(Chunk).where(Chunk.topic_id == topic_id).limit(1)).all()
        if db_chunks:
            from models.analysis_run import AnalysisRun
            from models.extracted_atom import ExtractedAtom

            run = AnalysisRun(topic_id=topic_id)
            session.add(run)
            session.commit()

            atom = ExtractedAtom(
                topic_id=topic_id,
                run_id=run.id,
                atom_type="character",
                stable_id="char_liming",
                canonical_name="李明",
                source_chunk_ids=json.dumps([db_chunks[0].id]),
                evidence_quotes=json.dumps(["少年李明出生在江南。"]),
                confidence=0.9,
            )
            session.add(atom)
            session.commit()

            resp = client.get(f"/api/topics/{topic_id}/entities/char_liming/evidence")
            assert resp.status_code == 200
            ev = resp.json()
            assert len(ev["atoms"]) >= 1

        # --- Similar scenes ---
        resp = client.get(
            f"/api/topics/{topic_id}/similar-scenes",
            params={"query": "少年", "limit": 3},
        )
        assert resp.status_code == 200

        # --- Cleanup ---
        resp = client.delete(f"/api/topics/{topic_id}")
        assert resp.status_code == 200

        resp = client.get("/api/providers")
        for p in resp.json().get("providers", []):
            if p["name"] == "smoke-epub-provider":
                client.delete(f"/api/providers/{p['id']}")


# ── Benchmarks ──


@pytest.mark.integration
class TestV03Benchmarks:
    def test_fts_rebuild_benchmark(self, client):
        """Measure FTS rebuild time."""
        # Use the full sample for more chunks
        resp = client.post("/api/topics", json={"name": "bench-fts"})
        assert resp.status_code == 201
        topic_id = resp.json()["id"]

        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": ("bench.txt", io.BytesIO(TXT_SAMPLE.encode("utf-8")))},
        )
        assert resp.status_code == 201
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

        # Get chunk count
        resp = client.get(f"/api/topics/{topic_id}/chunks")
        chunk_count = len(resp.json()["chunks"])

        # Direct FTS rebuild timing
        from db import get_session
        from main import app
        from services.fts_service import rebuild_topic_chunk_fts

        session_gen = app.dependency_overrides.get(get_session, get_session)
        session = next(session_gen())

        start = time.perf_counter()
        row_count = rebuild_topic_chunk_fts(topic_id, session)
        elapsed = time.perf_counter() - start

        assert row_count > 0
        print(f"\n  FTS rebuild: {row_count} rows from {chunk_count} chunks in {elapsed:.4f}s")

        # Cleanup
        client.delete(f"/api/topics/{topic_id}")

    def test_search_latency_benchmark(self, client):
        """Measure search latency for a representative query."""
        resp = client.post("/api/topics", json={"name": "bench-search"})
        assert resp.status_code == 201
        topic_id = resp.json()["id"]

        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": ("bench.txt", io.BytesIO(TXT_SAMPLE.encode("utf-8")))},
        )
        assert resp.status_code == 201
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

        # Warm up
        for _ in range(3):
            client.post(
                f"/api/topics/{topic_id}/search",
                json={"query": "张三", "limit": 5},
            )

        # Measure
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            resp = client.post(
                f"/api/topics/{topic_id}/search",
                json={"query": "李四", "limit": 5},
            )
            latencies.append(time.perf_counter() - start)
            assert resp.status_code == 200

        avg = sum(latencies) / len(latencies)
        print(
            f"\n  Search latency: avg={avg:.4f}s min={min(latencies):.4f}s max={max(latencies):.4f}s"
        )

        # Cleanup
        client.delete(f"/api/topics/{topic_id}")

    def test_retrieval_latency_benchmark(self, client):
        """Measure hybrid retrieval latency."""
        resp = client.post("/api/topics", json={"name": "bench-retrieve"})
        assert resp.status_code == 201
        topic_id = resp.json()["id"]

        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": ("bench.txt", io.BytesIO(TXT_SAMPLE.encode("utf-8")))},
        )
        assert resp.status_code == 201
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

        # Warm up
        for _ in range(3):
            client.post(
                f"/api/topics/{topic_id}/retrieve",
                json={"query": "张三", "top_k": 5},
            )

        # Measure
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            resp = client.post(
                f"/api/topics/{topic_id}/retrieve",
                json={"query": "修行 剑法", "top_k": 5},
            )
            latencies.append(time.perf_counter() - start)
            assert resp.status_code == 200

        avg = sum(latencies) / len(latencies)
        print(
            f"\n  Retrieval latency: avg={avg:.4f}s min={min(latencies):.4f}s max={max(latencies):.4f}s"
        )

        # Cleanup
        client.delete(f"/api/topics/{topic_id}")
