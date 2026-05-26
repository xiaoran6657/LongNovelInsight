"""v0.3 Step 2 — Upload Layer tests."""

import io
import zipfile

from fastapi.testclient import TestClient


def _make_epub_bytes(*, include_container: bool = True) -> bytes:
    """Build a minimal valid EPUB as bytes (valid zip with container.xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        if include_container:
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?>'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                "<rootfiles>"
                '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
                "</rootfiles>"
                "</container>",
            )
        # A minimal OPF to make it a well-formed EPUB (not strictly required for Step 2, but good practice)
        zf.writestr(
            "content.opf",
            '<?xml version="1.0"?>'
            '<package version="3.0" xmlns="http://www.idpf.org/2007/opf">'
            "<metadata>"
            "<dc:title xmlns:dc='http://purl.org/dc/elements/1.1/'>Test Book</dc:title>"
            "</metadata>"
            "<manifest/>"
            "<spine/>"
            "</package>",
        )
    return buf.getvalue()


def _create_topic(client: TestClient) -> str:
    resp = client.post("/api/topics", json={"name": "Upload Test"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_file(client: TestClient, topic_id: str, filename: str, content: bytes) -> dict:
    resp = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": (filename, io.BytesIO(content))},
    )
    return resp


# ── TXT regression ──


class TestTXTUploadRegression:
    def test_txt_upload_still_works(self, client):
        topic_id = _create_topic(client)
        txt = "Chapter 1\n\nHello world.\n\nChapter 2\n\nGoodbye."
        resp = _upload_file(client, topic_id, "test.txt", txt.encode("utf-8"))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["file_type"] == "txt"
        assert data["encoding"] in ("utf-8", "utf-8-sig")
        assert data["stored_filename"] == "original.txt"
        assert data["char_count"] > 0
        assert data["metadata_json"] is None

    def test_txt_upload_rejects_non_txt_extension(self, client):
        topic_id = _create_topic(client)
        resp = _upload_file(client, topic_id, "test.pdf", b"not a pdf")
        assert resp.status_code == 400
        assert "only .txt and .epub" in resp.json()["detail"].lower()

    def test_txt_upload_duplicate_409(self, client):
        topic_id = _create_topic(client)
        _upload_file(client, topic_id, "test.txt", b"hello world")
        resp = _upload_file(client, topic_id, "test2.txt", b"hello again")
        assert resp.status_code == 409

    def test_txt_upload_empty_rejected(self, client):
        topic_id = _create_topic(client)
        # Upload whitespace-only content
        resp = _upload_file(client, topic_id, "test.txt", b"   \n  \t  ")
        assert resp.status_code == 422


# ── EPUB upload ──


class TestEPUBUpload:
    def test_valid_epub_upload(self, client):
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes()
        resp = _upload_file(client, topic_id, "book.epub", epub_bytes)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["file_type"] == "epub"
        assert data["encoding"] == "epub"
        assert data["stored_filename"] == "original.epub"
        assert data["char_count"] == 0  # not parsed yet
        assert data["metadata_json"] is not None
        import json

        meta = json.loads(data["metadata_json"])
        assert meta["source_format"] == "epub"
        assert meta["parsing_warnings"] == []

    def test_epub_upload_sets_content_type(self, client):
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes()
        resp = _upload_file(client, topic_id, "book.epub", epub_bytes)
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "application/epub+zip"

    def test_invalid_zip_rejected(self, client):
        topic_id = _create_topic(client)
        resp = _upload_file(client, topic_id, "bad.epub", b"not a zip file at all")
        assert resp.status_code == 400
        assert "not a valid epub" in resp.json()["detail"].lower()

    def test_missing_container_xml_rejected(self, client):
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes(include_container=False)
        resp = _upload_file(client, topic_id, "nocontainer.epub", epub_bytes)
        assert resp.status_code == 400
        assert "missing meta-inf/container.xml" in resp.json()["detail"].lower()

    def test_epub_duplicate_document_409(self, client):
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes()
        _upload_file(client, topic_id, "book1.epub", epub_bytes)
        resp = _upload_file(client, topic_id, "book2.epub", epub_bytes)
        assert resp.status_code == 409

    def test_epub_file_exceeds_max_size(self, client, monkeypatch):
        import config

        monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 100)
        topic_id = _create_topic(client)
        big = b"x" * 200
        resp = _upload_file(client, topic_id, "big.epub", big)
        assert resp.status_code == 413

    def test_epub_document_delete_removes_file(self, client):
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes()
        resp = _upload_file(client, topic_id, "book.epub", epub_bytes)
        assert resp.status_code == 201

        # Verify file was written
        from services.storage import get_source_dir

        src_dir = get_source_dir(topic_id)
        epub_path = src_dir / "original.epub"
        assert epub_path.exists()

        # Delete document
        resp = client.delete(f"/api/topics/{topic_id}/documents/current")
        assert resp.status_code == 200

        # File should be removed
        assert not epub_path.exists()

    def test_epub_then_delete_then_upload_again(self, client):
        """After deleting an EPUB, a new document can be uploaded."""
        topic_id = _create_topic(client)
        epub_bytes = _make_epub_bytes()

        resp = _upload_file(client, topic_id, "book.epub", epub_bytes)
        assert resp.status_code == 201

        client.delete(f"/api/topics/{topic_id}/documents/current")

        resp = _upload_file(client, topic_id, "newbook.epub", epub_bytes)
        assert resp.status_code == 201


# ── Mixed format scenarios ──


class TestMixedFormatUpload:
    def test_epub_then_txt_after_delete(self, client):
        topic_id = _create_topic(client)

        resp = _upload_file(client, topic_id, "book.epub", _make_epub_bytes())
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "epub"

        client.delete(f"/api/topics/{topic_id}/documents/current")

        resp = _upload_file(client, topic_id, "book.txt", b"hello world")
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "txt"

    def test_txt_then_epub_after_delete(self, client):
        topic_id = _create_topic(client)

        resp = _upload_file(client, topic_id, "book.txt", b"hello world")
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "txt"

        client.delete(f"/api/topics/{topic_id}/documents/current")

        resp = _upload_file(client, topic_id, "book.epub", _make_epub_bytes())
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "epub"
