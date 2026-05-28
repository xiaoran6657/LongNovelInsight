"""v0.3 Step 6 — Search / Metadata / Locator API tests."""

import io

from fastapi.testclient import TestClient


def _create_topic(client: TestClient, name: str = "Search Test") -> str:
    resp = client.post("/api/topics", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_txt(client: TestClient, topic_id: str, text: str) -> None:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", io.BytesIO(text.encode("utf-8")))},
    )
    assert resp.status_code == 201, resp.text


def _parse(client: TestClient, topic_id: str) -> None:
    resp = client.post(f"/api/topics/{topic_id}/parse")
    assert resp.status_code == 200, resp.text


# ── Metadata API ──


class TestDocumentMetadata:
    def test_txt_metadata_null(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nHello world.\n")
        resp = client.get(f"/api/topics/{topic_id}/documents/current/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_type"] == "txt"
        assert data["metadata"] == {}

    def test_epub_metadata_parsed(self, client):
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?>'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                "<rootfiles>"
                '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
                "</rootfiles>"
                "</container>",
            )
        epub_bytes = buf.getvalue()

        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/documents/upload",
            files={"file": ("test.epub", io.BytesIO(epub_bytes))},
        )
        assert resp.status_code == 201

        resp = client.get(f"/api/topics/{topic_id}/documents/current/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_type"] == "epub"
        assert data["metadata"]["source_format"] == "epub"
        assert "parsing_warnings" in data["metadata"]

    def test_metadata_topic_not_found(self, client):
        resp = client.get("/api/topics/nonexistent-id/documents/current/metadata")
        assert resp.status_code == 404

    def test_metadata_no_document(self, client):
        topic_id = _create_topic(client)
        resp = client.get(f"/api/topics/{topic_id}/documents/current/metadata")
        assert resp.status_code == 404


# ── Search API ──


class TestSearchAPI:
    def test_english_search(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nThe quick brown fox jumps over the lazy dog.\n")
        _parse(client, topic_id)

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "quick fox", "limit": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "quick fox"
        assert len(data["results"]) >= 1
        assert data["trace_id"] is None
        for r in data["results"]:
            assert "chunk_id" in r
            assert "snippet" in r
            assert "score" in r
            assert r["method"] in ("fts", "keyword_fallback")

    def test_cjk_search(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "第一章\n\n刘备和曹操相遇于赤壁。\n")
        _parse(client, topic_id)

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "刘备曹操", "limit": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1

    def test_search_no_results(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nHello world.\n")
        _parse(client, topic_id)

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "xyznonexistent12345", "limit": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_include_snippets_false(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nThe quick brown fox.\n")
        _parse(client, topic_id)

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "quick", "include_snippets": False},
        )
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["snippet"] == ""

    def test_filter_by_methods(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nThe quick brown fox.\n")
        _parse(client, topic_id)

        # Only keyword_fallback — calls fallback primitive directly
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "quick", "methods": ["keyword_fallback"]},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        for r in results:
            assert r["method"] == "keyword_fallback"

        # Only fts — calls FTS primitive directly
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "quick", "methods": ["fts"]},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        for r in results:
            assert r["method"] == "fts"

    def test_empty_query_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "", "limit": 10},
        )
        assert resp.status_code == 422

    def test_missing_query_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"limit": 10},
        )
        assert resp.status_code == 422

    def test_query_too_long_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "x" * 501, "limit": 10},
        )
        assert resp.status_code == 422

    def test_limit_out_of_range_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "hello", "limit": 0},
        )
        assert resp.status_code == 422

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "hello", "limit": 101},
        )
        assert resp.status_code == 422

    def test_invalid_methods_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "hello", "methods": ["invalid"]},
        )
        assert resp.status_code == 422

    def test_mixed_type_methods_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "hello", "methods": ["bad", 123]},
        )
        assert resp.status_code == 422

    def test_empty_methods_422(self, client):
        topic_id = _create_topic(client)
        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "hello", "methods": []},
        )
        assert resp.status_code == 422

    def test_search_topic_not_found(self, client):
        resp = client.post(
            "/api/topics/nonexistent-id/search",
            json={"query": "hello", "limit": 10},
        )
        assert resp.status_code == 404

    def test_default_limit_and_methods(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nThe quick brown fox.\n")
        _parse(client, topic_id)

        resp = client.post(
            f"/api/topics/{topic_id}/search",
            json={"query": "quick"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1


# ── Locator API ──


class TestLocatorAPI:
    def test_locator_basic(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nHello world.\n")
        _parse(client, topic_id)

        # Get chunks to find a chunk_id
        chunks_resp = client.get(f"/api/topics/{topic_id}/chunks?limit=1")
        assert chunks_resp.status_code == 200
        chunk_id = chunks_resp.json()["chunks"][0]["id"]

        resp = client.get(f"/api/topics/{topic_id}/chunks/{chunk_id}/locator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_id"] == chunk_id
        assert data["topic_id"] == topic_id
        assert "chapter_index" in data
        assert "chunk_index" in data
        assert "locator" in data
        assert len(data["excerpt"]) > 0
        assert len(data["excerpt"]) <= 200

    def test_locator_chunk_not_found(self, client):
        topic_id = _create_topic(client)
        resp = client.get(f"/api/topics/{topic_id}/chunks/nonexistent-chunk/locator")
        assert resp.status_code == 404

    def test_locator_wrong_topic(self, client):
        topic_id1 = _create_topic(client, "Topic 1")
        _upload_txt(client, topic_id1, "Chapter 1\n\nHello world.\n")
        _parse(client, topic_id1)

        chunks_resp = client.get(f"/api/topics/{topic_id1}/chunks?limit=1")
        chunk_id = chunks_resp.json()["chunks"][0]["id"]

        # Try to access chunk from a different topic
        topic_id2 = _create_topic(client, "Topic 2")
        resp = client.get(f"/api/topics/{topic_id2}/chunks/{chunk_id}/locator")
        assert resp.status_code == 404
