import io


def _create_topic(client, name="Parse Test"):
    r = client.post("/api/topics", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _upload_txt(client, topic_id, content=None):
    if content is None:
        content = "第一章 开篇\n这是第一章的内容。\n第二章 发展\n这是第二章的内容。\n"
    r = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("novel.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
    )
    assert r.status_code == 201
    return r.json()


def _parse(client, topic_id):
    return client.post(f"/api/topics/{topic_id}/parse")


# ── Parse ──


def test_parse_success(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    r = _parse(client, tid)
    assert r.status_code == 200
    data = r.json()
    assert data["chapter_count"] >= 1
    assert data["chunk_count"] >= 1
    assert data["char_count"] > 0
    assert data["estimated_tokens"] > 0


def test_parse_creates_chapters(client):
    content = "第一章 开始\n内容A\n第二章 中间\n内容B\n第三章 结束\n内容C\n"
    tid = _create_topic(client)
    _upload_txt(client, tid, content=content)
    _parse(client, tid)
    r = client.get(f"/api/topics/{tid}/chapters")
    assert r.status_code == 200
    chapters = r.json()["chapters"]
    assert len(chapters) == 3
    assert chapters[0]["chapter_index"] == 0
    assert chapters[1]["chapter_index"] == 1
    assert chapters[2]["chapter_index"] == 2


def test_parse_creates_chunks(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)
    r = client.get(f"/api/topics/{tid}/chunks")
    assert r.status_code == 200
    chunks = r.json()["chunks"]
    assert len(chunks) >= 1


def test_parse_no_document_404(client):
    tid = _create_topic(client)
    r = _parse(client, tid)
    assert r.status_code == 404


def test_parse_nonexistent_topic_404(client):
    r = client.post("/api/topics/nonexistent/parse")
    assert r.status_code == 404


def test_reparse_is_idempotent(client):
    content = "第一章 开始\n内容\n第二章 结束\n内容\n"
    tid = _create_topic(client)
    _upload_txt(client, tid, content=content)

    _parse(client, tid)
    r1 = client.get(f"/api/topics/{tid}/chapters")
    count1 = len(r1.json()["chapters"])

    _parse(client, tid)
    r2 = client.get(f"/api/topics/{tid}/chapters")
    count2 = len(r2.json()["chapters"])

    assert count1 == count2


# ── Chunks with text control ──


def test_chunks_include_text_false(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)
    r = client.get(f"/api/topics/{tid}/chunks?include_text=false")
    chunks = r.json()["chunks"]
    assert len(chunks) >= 1
    assert all(c["text"] == "" for c in chunks)


def test_chunks_include_text_true(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)
    r = client.get(f"/api/topics/{tid}/chunks?include_text=true")
    chunks = r.json()["chunks"]
    assert len(chunks) >= 1
    assert all(len(c["text"]) > 0 for c in chunks)


def test_chunks_default_no_text(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)
    r = client.get(f"/api/topics/{tid}/chunks")
    chunks = r.json()["chunks"]
    assert len(chunks) >= 1
    assert all(c["text"] == "" for c in chunks)


def test_chunks_pagination(client):
    content = ""
    for i in range(20):
        content += f"第{i + 1}章 章节{i + 1}\n这是第{i + 1}章的内容。\n"
    tid = _create_topic(client)
    _upload_txt(client, tid, content=content)
    _parse(client, tid)

    r = client.get(f"/api/topics/{tid}/chunks?limit=5&offset=0")
    assert len(r.json()["chunks"]) == 5


# ── Storage ──


def test_get_storage(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)

    r = client.get(f"/api/topics/{tid}/storage")
    assert r.status_code == 200
    data = r.json()
    assert data["total_disk_usage_bytes"] >= 0
    assert data["database_size_bytes"] >= 0
    assert len(data["topics"]) == 1
    assert data["topics"][0]["novel_size_bytes"] > 0
    assert data["topics"][0]["chunks_size_bytes"] > 0
    assert data["topics"][0]["total_bytes"] >= data["topics"][0]["novel_size_bytes"]


# ── Long text chunking ──


def test_long_text_many_chunks(client):
    content = "第一章 长篇\n" + ("长" * 15000) + "\n第二章 结束\n" + ("短" * 100)
    tid = _create_topic(client)
    _upload_txt(client, tid, content=content)
    _parse(client, tid)

    r = client.get(f"/api/topics/{tid}/chunks")
    chunks = r.json()["chunks"]
    # The first chapter (15000 chars) should be split into ~4 chunks
    assert len(chunks) >= 2


def test_chunks_have_estimated_tokens(client):
    tid = _create_topic(client)
    _upload_txt(client, tid)
    _parse(client, tid)

    r = client.get(f"/api/topics/{tid}/chunks?include_text=true")
    for c in r.json()["chunks"]:
        assert c["estimated_tokens"] > 0
