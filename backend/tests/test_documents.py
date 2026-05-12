import io


def _create_topic(client, name="Doc Test"):
    r = client.post("/api/topics", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client, topic_id, filename="test.txt", content=None, content_type="text/plain"):
    if content is None:
        content = io.BytesIO(b"Hello, World!\nThis is a test.\n")
    elif isinstance(content, bytes):
        content = io.BytesIO(content)
    else:
        content = io.BytesIO(content)
    return client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": (filename, content, content_type)},
    )


# ── UTF-8 ──


def test_upload_utf8_success(client):
    tid = _create_topic(client)
    r = _upload(client, tid, content="Hello World\n".encode("utf-8"))
    assert r.status_code == 201
    assert r.json()["encoding"] in ("utf-8-sig", "utf-8")


# ── UTF-8-SIG ──


def test_upload_utf8_sig_success(client):
    tid = _create_topic(client)
    r = _upload(client, tid, content="Hello\n".encode("utf-8-sig"))
    assert r.status_code == 201
    assert r.json()["encoding"] == "utf-8-sig"


# ── GBK ──


def test_upload_gbk_success(client):
    tid = _create_topic(client)
    text = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。"
    r = _upload(client, tid, content=text.encode("gbk"))
    assert r.status_code == 201
    assert r.json()["encoding"] in ("gbk", "gb18030")


def test_upload_gbk_saved_as_utf8(client):
    import config

    tid = _create_topic(client)
    text = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。"
    _upload(client, tid, content=text.encode("gbk"))

    saved_path = config.DATA_DIR / "topics" / tid / "source" / "original.txt"
    assert saved_path.exists()
    saved_text = saved_path.read_text(encoding="utf-8")
    assert "第一章" in saved_text
    assert "张三" in saved_text


def test_upload_gbk_parse_works(client):

    tid = _create_topic(client)
    text = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。"
    _upload(client, tid, content=text.encode("gbk"))

    r = client.post(f"/api/topics/{tid}/parse")
    assert r.status_code == 200
    assert r.json()["chapter_count"] == 2

    r = client.get(f"/api/topics/{tid}/chapters")
    chapters = r.json()["chapters"]
    assert chapters[0]["title"] == "第一章 风起"
    assert chapters[1]["title"] == "第二章 雨落"


# ── GB18030 ──


def test_upload_gb18030_success(client):
    tid = _create_topic(client)
    text = "第一章 测试\n内容行。"
    r = _upload(client, tid, content=text.encode("gb18030"))
    assert r.status_code == 201
    assert r.json()["encoding"] in ("gb18030", "gbk")


# ── UTF-16 ──


def test_upload_utf16_success(client):
    tid = _create_topic(client)
    text = "第一章 内容\n第二章 内容"
    r = _upload(client, tid, content=text.encode("utf-16"))
    assert r.status_code == 201
    assert r.json()["encoding"] in ("utf-16", "utf-16-le", "utf-16-be")


# ── Document.encoding ──


def test_document_encoding_reflects_source(client):
    tid = _create_topic(client)
    text = "测试内容"
    r = _upload(client, tid, content=text.encode("gbk"))
    assert r.status_code == 201
    doc_encoding = r.json()["encoding"]
    # GBK text may decode as gb18030 (superset)
    assert doc_encoding in ("gbk", "gb18030")


# ── Random binary ──


def test_random_binary_returns_400(client):
    tid = _create_topic(client)
    bad = bytes(range(256))
    r = _upload(client, tid, content=bad)
    assert r.status_code == 400
    assert "encoding" in r.json()["detail"].lower()


# ── Duplicate ──


def test_upload_duplicate_409(client):
    tid = _create_topic(client)
    _upload(client, tid, content="第一章\n".encode("utf-8"))
    r = _upload(client, tid, content="第二章\n".encode("utf-8"), filename="test2.txt")
    assert r.status_code == 409


# ── Delete ──


def test_delete_document_removes_file(client):
    import config

    tid = _create_topic(client)
    _upload(client, tid, content="Hello\n".encode("utf-8"))

    r = client.delete(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    saved = config.DATA_DIR / "topics" / tid / "source" / "original.txt"
    assert not saved.exists()

    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404


def test_delete_updates_storage_bytes(client):
    tid = _create_topic(client)
    _upload(client, tid, content="Hello\n".encode("utf-8"))

    r = client.get(f"/api/topics/{tid}")
    assert r.json()["storage_bytes"] > 0

    client.delete(f"/api/topics/{tid}/documents/current")

    r = client.get(f"/api/topics/{tid}")
    assert r.json()["storage_bytes"] == 0


# ── General ──


def test_get_current_document(client):
    tid = _create_topic(client)
    _upload(client, tid, content="Hello\n".encode("utf-8"))
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["original_filename"] == "test.txt"


def test_get_current_404_no_topic(client):
    r = client.get("/api/topics/nonexistent/documents/current")
    assert r.status_code == 404


def test_get_current_404_no_document(client):
    tid = _create_topic(client)
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404


def test_upload_nonexistent_topic_404(client):
    r = _upload(client, "nonexistent", content=b"data")
    assert r.status_code == 404


def test_upload_non_txt_400(client):
    tid = _create_topic(client)
    r = client.post(
        f"/api/topics/{tid}/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
    )
    assert r.status_code == 400


def test_file_size_bytes_records_original(client):
    tid = _create_topic(client)
    orig = "第一章".encode("gbk")
    r = _upload(client, tid, content=orig)
    assert r.status_code == 201
    assert r.json()["file_size_bytes"] == len(orig)


def test_char_count_records_decoded(client):
    tid = _create_topic(client)
    text = "第一章 风起\n张三走进长安城。"
    r = _upload(client, tid, content=text.encode("gbk"))
    assert r.status_code == 201
    assert r.json()["char_count"] == len(text)
