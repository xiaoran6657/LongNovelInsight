import io


def _create_topic(client, name="Test Topic"):
    r = client.post("/api/topics", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client, topic_id, filename="test.txt", content=b"Hello, World!\nThis is a test.\n"):
    return client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


def test_upload_txt_success(client):
    tid = _create_topic(client)
    r = _upload(client, tid)
    assert r.status_code == 201
    data = r.json()
    assert data["original_filename"] == "test.txt"
    assert data["file_type"] == "txt"
    assert data["file_size_bytes"] > 0
    assert data["char_count"] > 0
    assert data["status"] == "uploaded"
    assert "id" in data


def test_upload_txt_file_exists_on_disk(client):

    import config

    tid = _create_topic(client)
    _upload(client, tid)
    expected = config.DATA_DIR / "topics" / tid / "source" / "original.txt"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == "Hello, World!\nThis is a test.\n"


def test_get_current_document(client):
    tid = _create_topic(client)
    _upload(client, tid)
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["original_filename"] == "test.txt"


def test_get_current_document_404_no_topic(client):
    r = client.get("/api/topics/nonexistent/documents/current")
    assert r.status_code == 404


def test_get_current_document_404_no_document(client):
    tid = _create_topic(client)
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404


def test_upload_duplicate_409(client):
    tid = _create_topic(client)
    _upload(client, tid)
    r = _upload(client, tid, filename="test2.txt")
    assert r.status_code == 409


def test_upload_nonexistent_topic_404(client):
    r = _upload(client, "nonexistent")
    assert r.status_code == 404


def test_upload_non_txt_400(client):
    tid = _create_topic(client)
    r = client.post(
        f"/api/topics/{tid}/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_non_utf8_400(client):
    tid = _create_topic(client)
    # Create bytes that are not valid UTF-8
    bad_bytes = b"\xff\xfe\x00\x00\xff\xfe"
    r = client.post(
        f"/api/topics/{tid}/documents/upload",
        files={"file": ("bad.txt", io.BytesIO(bad_bytes), "text/plain")},
    )
    assert r.status_code == 400


def test_delete_document(client):

    import config

    tid = _create_topic(client)
    _upload(client, tid)
    r = client.delete(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert r.json()["freed_bytes"] > 0

    # Verify file removed
    expected = config.DATA_DIR / "topics" / tid / "source" / "original.txt"
    assert not expected.exists()

    # Verify GET returns 404 after delete
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404


def test_delete_document_404_no_topic(client):
    r = client.delete("/api/topics/nonexistent/documents/current")
    assert r.status_code == 404


def test_delete_document_404_no_document(client):
    tid = _create_topic(client)
    r = client.delete(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404


def test_storage_bytes_updated_on_upload(client):
    tid = _create_topic(client)
    _upload(client, tid)

    r = client.get(f"/api/topics/{tid}")
    assert r.status_code == 200
    assert r.json()["storage_bytes"] > 0


def test_storage_bytes_updated_on_delete(client):
    tid = _create_topic(client)
    _upload(client, tid)
    client.delete(f"/api/topics/{tid}/documents/current")

    r = client.get(f"/api/topics/{tid}")
    assert r.status_code == 200
    assert r.json()["storage_bytes"] == 0
