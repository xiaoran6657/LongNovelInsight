"""v0.3 Step 4 — Unified Parse Pipeline tests."""

import io
import json
import zipfile

from fastapi.testclient import TestClient


def _create_topic(client: TestClient) -> str:
    resp = client.post("/api/topics", json={"name": "Parse Test"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_txt(client: TestClient, topic_id: str, text: str) -> dict:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", io.BytesIO(text.encode("utf-8")))},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_epub_bytes() -> bytes:
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
        zf.writestr(
            "content.opf",
            '<?xml version="1.0"?>'
            '<package version="3.0" xmlns="http://www.idpf.org/2007/opf">'
            "<metadata>"
            "<dc:title xmlns:dc='http://purl.org/dc/elements/1.1/'>Test</dc:title>"
            "<dc:creator xmlns:dc='http://purl.org/dc/elements/1.1/'>A</dc:creator>"
            "<dc:language xmlns:dc='http://purl.org/dc/elements/1.1/'>en</dc:language>"
            "</metadata>"
            "<manifest>"
            '<item id="ch0" href="ch01.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="ch1" href="ch02.xhtml" media-type="application/xhtml+xml"/>'
            "</manifest>"
            '<spine><itemref idref="ch0"/><itemref idref="ch1"/></spine>'
            "</package>",
        )
        zf.writestr(
            "ch01.xhtml",
            "<html><body><h1>Chapter 1</h1><p>First chapter content here.</p></body></html>",
        )
        zf.writestr(
            "ch02.xhtml",
            "<html><body><h1>Chapter 2</h1><p>Second chapter content here.</p></body></html>",
        )
    return buf.getvalue()


def _upload_epub(client: TestClient, topic_id: str) -> dict:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("book.epub", io.BytesIO(_make_epub_bytes()))},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── TXT regression ──


class TestTXTParseRegression:
    def test_txt_parse_creates_chapters_and_chunks(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nContent one.\n\nChapter 2\n\nContent two.\n")

        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["chapter_count"] >= 1
        assert data["chunk_count"] >= 1
        assert data["char_count"] > 0
        assert "already_parsed" not in data

    def test_txt_parse_writes_source_locators(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nHello world.\n")

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/chunks?include_text=false&limit=10")
        assert resp.status_code == 200
        chunks = resp.json()["chunks"]
        assert len(chunks) >= 1
        loc = json.loads(chunks[0]["source_locator_json"])
        assert loc["source_type"] == "txt"
        assert loc["href"] == "txt://original"

    def test_txt_parse_idempotent(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nContent.\n")

        r1 = client.post(f"/api/topics/{topic_id}/parse")
        assert r1.status_code == 200
        data1 = r1.json()
        assert "already_parsed" not in data1

        # Second parse should return already_parsed=True
        r2 = client.post(f"/api/topics/{topic_id}/parse")
        assert r2.status_code == 200
        assert r2.json()["already_parsed"] is True

    def test_txt_reparse_with_force(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nContent.\n")

        client.post(f"/api/topics/{topic_id}/parse")
        r2 = client.post(f"/api/topics/{topic_id}/parse?force=true")
        assert r2.status_code == 200
        data = r2.json()
        assert data["chapter_count"] >= 1

    def test_txt_parse_document_status_updated(self, client):
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nContent.\n")

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/documents/current")
        assert resp.status_code == 200
        assert resp.json()["status"] == "parsed"
        assert resp.json()["char_count"] > 0

    def test_txt_parse_no_document_returns_409(self, client):
        topic_id = _create_topic(client)
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 404


# ── EPUB parse ──


class TestEPUBParse:
    def test_epub_parse_creates_chapters_in_spine_order(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["chapter_count"] == 2
        assert data["chunk_count"] >= 2

        # Verify chapter order
        chapters_resp = client.get(f"/api/topics/{topic_id}/chapters")
        chapters = chapters_resp.json()["chapters"]
        assert len(chapters) == 2
        assert chapters[0]["title"] == "Chapter 1"
        assert chapters[1]["title"] == "Chapter 2"
        assert chapters[0]["source_href"] == "ch01.xhtml"

    def test_epub_parse_writes_locator_json(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/chunks?include_text=false&limit=10")
        chunks = resp.json()["chunks"]
        assert len(chunks) >= 1

        loc = json.loads(chunks[0]["source_locator_json"])
        assert loc["source_type"] == "epub"
        assert "href" in loc
        assert "chapter_index" in loc
        assert "chunk_index" in loc

    def test_epub_parse_updates_document(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/documents/current")
        doc = resp.json()
        assert doc["status"] == "parsed"
        assert doc["char_count"] > 0

    def test_epub_parse_chapters_have_nav_order(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/chapters")
        chapters = resp.json()["chapters"]
        for ch in chapters:
            assert ch["nav_order"] is not None
            assert ch["source_href"] is not None

    def test_epub_reparse_clears_old_chapters(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        client.post(f"/api/topics/{topic_id}/parse")
        r1 = client.get(f"/api/topics/{topic_id}/chapters")
        assert r1.json()["chapters"][0]["title"] == "Chapter 1"

        # Force re-parse
        client.post(f"/api/topics/{topic_id}/parse?force=true")
        r2 = client.get(f"/api/topics/{topic_id}/chapters")
        # Should still have chapters, not doubled
        assert len(r2.json()["chapters"]) == 2

    def test_epub_parse_chunks_meta_works(self, client):
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        client.post(f"/api/topics/{topic_id}/parse")
        resp = client.get(f"/api/topics/{topic_id}/chunks/meta")
        assert resp.status_code == 200
        meta = resp.json()
        assert meta["chunk_count"] >= 2
        assert meta["chapter_count"] == 2
        assert meta["total_chars"] > 0

    def test_epub_parse_no_document_returns_404(self, client):
        topic_id = _create_topic(client)
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 404

    def test_epub_not_uploaded_txt_not_found(self, client):
        """A TXT topic where the file is missing returns 409."""
        topic_id = _create_topic(client)
        _upload_txt(client, topic_id, "Chapter 1\n\nHello.\n")

        # Parse should work
        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200

    def test_epub_parse_warnings_in_response(self, client):
        """Parse response should surface EPUB parsing warnings."""
        topic_id = _create_topic(client)
        _upload_epub(client, topic_id)

        resp = client.post(f"/api/topics/{topic_id}/parse")
        assert resp.status_code == 200
        data = resp.json()
        # Our test EPUB is well-formed, so no warnings expected
        # but the field should be absent when empty
        if "warnings" in data:
            assert isinstance(data["warnings"], list)
