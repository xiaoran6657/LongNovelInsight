import io

import pytest


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


# ── Empty / whitespace rejection ──


def test_upload_empty_txt_returns_422(client):
    tid = _create_topic(client)
    r = _upload(client, tid, content=b"")
    assert r.status_code == 422
    assert "no meaningful text" in r.json()["detail"].lower()


def test_upload_whitespace_only_txt_returns_422(client):
    tid = _create_topic(client)
    r = _upload(client, tid, content="   \n  \t  \n  ".encode("utf-8"))
    assert r.status_code == 422
    assert "no meaningful text" in r.json()["detail"].lower()


# ── Document delete cascade ──


def test_delete_document_cascades_derived_data(client):
    """Deleting a document removes chapters/chunks/jobs/chat/analysis."""
    tid = _create_topic(client, name="DocCascade")

    # Upload
    novel = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。"
    _upload(client, tid, content=novel.encode("utf-8"))

    # Parse
    client.post(f"/api/topics/{tid}/parse")

    # Create chat session
    r = client.post(f"/api/topics/{tid}/chat/sessions", json={"title": "Test Chat"})
    session_id = r.json()["id"]

    # Run analysis (stub job)
    client.post(f"/api/topics/{tid}/analysis/jobs")

    # Verify derived data exists
    assert len(client.get(f"/api/topics/{tid}/chapters").json()["chapters"]) >= 1
    assert len(client.get(f"/api/topics/{tid}/chunks").json()["chunks"]) >= 1
    assert len(client.get(f"/api/topics/{tid}/analysis/jobs").json()["jobs"]) >= 1
    assert len(client.get(f"/api/topics/{tid}/chat/sessions").json()["sessions"]) >= 1
    assert client.get(f"/api/chat/sessions/{session_id}/messages").status_code == 200

    # Delete document
    r = client.delete(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # Verify derived data cleaned up
    assert len(client.get(f"/api/topics/{tid}/chapters").json()["chapters"]) == 0
    assert len(client.get(f"/api/topics/{tid}/chunks").json()["chunks"]) == 0
    assert len(client.get(f"/api/topics/{tid}/analysis/jobs").json()["jobs"]) == 0
    assert len(client.get(f"/api/topics/{tid}/chat/sessions").json()["sessions"]) == 0

    # Document gone
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 404

    # Topic still exists
    r = client.get(f"/api/topics/{tid}")
    assert r.status_code == 200
    assert r.json()["storage_bytes"] == 0
    assert r.json()["document"] is None


def test_reupload_after_delete_works(client):
    """After deleting a document, re-upload should succeed."""
    tid = _create_topic(client)
    _upload(client, tid, content="第一章\n".encode("utf-8"))
    client.delete(f"/api/topics/{tid}/documents/current")

    # Re-upload should work
    r = _upload(client, tid, content="新内容\n".encode("utf-8"))
    assert r.status_code == 201
    assert r.json()["status"] == "uploaded"

    # Verify there's exactly one document
    r = client.get(f"/api/topics/{tid}/documents/current")
    assert r.status_code == 200
    assert r.json()["original_filename"] == "test.txt"


# ── Path safety ──


def test_safe_delete_blocks_path_traversal(monkeypatch, tmp_path):
    """safe_delete_file must refuse to delete files outside DATA_DIR."""
    from services import storage

    inside_dir = tmp_path / "data"
    inside_dir.mkdir()
    monkeypatch.setattr(storage, "_data_dir", lambda: inside_dir.resolve())

    # File inside data dir — should work
    safe_file = inside_dir / "topics" / "t1" / "source" / "original.txt"
    safe_file.parent.mkdir(parents=True, exist_ok=True)
    safe_file.write_text("hello", encoding="utf-8")

    result = storage.safe_delete_file(safe_file)
    assert result is True
    assert not safe_file.exists()

    # File outside data dir — must raise
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("danger", encoding="utf-8")

    with pytest.raises(ValueError, match="Path traversal"):
        storage.safe_delete_file(outside_file)

    assert outside_file.exists()


def test_delete_document_cascades_v2_data(engine):
    """Deleting current document should remove v2 AnalysisRun/Extraction/Atom/Output."""
    from sqlmodel import Session, select

    from models.analysis_output import AnalysisOutput
    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.extracted_atom import ExtractedAtom
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.document_service import delete_current_document

    with Session(engine) as session:
        prov = ModelProvider(
            name="DocCascadeV2 P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="DocCascadeV2", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=10,
            char_count=10,
            status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_index=0,
            title="Ch1",
            start_char=0,
            end_char=10,
            char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="t",
            start_char=0,
            end_char=1,
            char_count=1,
            estimated_tokens=1,
        )
        session.add(ck)
        session.flush()
        ck_id = ck.id
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = AnalysisRun(topic_id=tid, mode="preview")
        session.add(run)
        session.flush()
        rid = run.id
        ext = LocalExtraction(run_id=rid, topic_id=tid, chunk_id=ck_id, status="succeeded")
        session.add(ext)
        session.flush()
        atom = ExtractedAtom(
            run_id=rid,
            topic_id=tid,
            local_extraction_id=ext.id,
            chunk_id=ck_id,
            atom_type="character",
            stable_id="char_x",
        )
        session.add(atom)
        session.flush()
        ao = AnalysisOutput(
            topic_id=tid,
            run_id=rid,
            output_type="characters",
            title="Test",
            content_json="{}",
            source_chunk_ids="[]",
            evidence_quotes="[]",
            confidence=0.9,
        )
        session.add(ao)
        session.commit()

    # Delete current document
    with Session(engine) as session:
        delete_current_document(tid, session)

    # Verify topic still exists but v2 rows are gone
    with Session(engine) as session:
        topic = session.get(Topic, tid)
        assert topic is not None
        assert len(session.exec(select(AnalysisRun).where(AnalysisRun.topic_id == tid)).all()) == 0
        assert (
            len(session.exec(select(LocalExtraction).where(LocalExtraction.topic_id == tid)).all())
            == 0
        )
        assert (
            len(session.exec(select(ExtractedAtom).where(ExtractedAtom.topic_id == tid)).all()) == 0
        )
        assert (
            len(session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == tid)).all())
            == 0
        )
