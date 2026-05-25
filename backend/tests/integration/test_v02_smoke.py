"""v0.2 end-to-end smoke test — runs against a live backend with real LLM.

Start the backend server before running:
    uvicorn main:app --port 8000

Then run with pytest:
    pytest tests/integration/test_v02_smoke.py -v -s -m integration

Or run directly:
    python tests/integration/test_v02_smoke.py
"""

from __future__ import annotations

import time
import uuid

import pytest

BASE = "http://127.0.0.1:8000"
POLL_INTERVAL = 3
MAX_WAIT = 300

SAMPLE = (
    "第一章 长安初遇\n\n"
    "长安城的秋日格外清爽，街道两旁的梧桐叶泛着金黄。\n\n"
    "张三背着行囊，踏入了这座传说中的都城。"
    "他在城门口站了许久，望着熙熙攘攘的人群和巍峨的城墙，心中涌起一股难以言说的激动。\n\n"
    '"这就是长安啊。"他自言自语道。\n\n'
    "街边的小贩吆喝着，卖糖葫芦的老汉推着车从人群中穿过。"
    "张三摸了摸怀中的书信，那是师父临终前交给他的，信封上只写了"
    '"长安李四收"四个字。\n\n'
    "他问了几个人，终于在东市找到了李四的住处。"
    "那是一座并不起眼的小院，门前种着两棵桂花树，正值花开时节，香气扑鼻。\n\n"
    "李四是个四十来岁的中年人，面容清癯，眼神却格外锐利。"
    "他看了信后，沉默良久，最后对张三说："
    '"你师父是我的救命恩人。既然他让你来找我，你就在我这里住下吧。"\n\n'
    "张三感激不尽，连连道谢。\n\n"
    '李四摆摆手："不必客气。不过你师父在信中说，'
    '你天资聪颖，但性子急躁。修行之路，最忌讳的就是急躁。"\n\n'
    '"大师教训得是。"张三低头道。\n\n'
    '"我不是什么大师，"李四笑了笑，"我只是个普通的读书人。'
    '不过你师父托付的事，我会尽力去做。"\n\n'
    "从此，张三便在李四家中住了下来，开始了他在长安城的修行生涯。\n"
)


@pytest.fixture(scope="module")
def api():
    """Return an httpx client connected to the running backend."""
    import httpx

    client = httpx.Client(timeout=30, base_url=BASE)
    for _ in range(10):
        try:
            r = client.get("/api/health")
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Backend not reachable at " + BASE)
    yield client
    client.close()


@pytest.mark.integration
def test_v02_smoke_pipeline(api):
    """Full v0.2 pipeline in a single test: upload -> parse -> preview analysis -> outputs."""

    # --- Health ---
    r = api.get("/api/health")
    assert r.status_code == 200
    assert r.json()["version"] == "0.2.0-dev"

    # --- Provider ---
    r = api.get("/api/providers")
    assert r.status_code == 200
    providers = r.json()["providers"]
    assert len(providers) > 0, "Need at least one provider with real API key"
    provider = providers[0]

    # --- Create topic ---
    name = f"smoke-{uuid.uuid4().hex[:8]}"
    r = api.post("/api/topics", json={"name": name, "provider_id": provider["id"]})
    assert r.status_code == 201, r.text
    topic = r.json()
    tid = topic["id"]

    try:
        # --- Upload ---
        r = api.post(
            f"/api/topics/{tid}/documents/upload",
            files={"file": ("smoke.txt", SAMPLE.encode("utf-8"), "text/plain")},
        )
        assert r.status_code in (200, 201), r.text
        assert r.json()["status"] in ("uploaded", "parsed")

        # --- Parse ---
        r = api.post(f"/api/topics/{tid}/parse")
        assert r.status_code == 200, r.text
        assert r.json()["chunk_count"] > 0, f"No chunks: {r.json()}"

        # --- Config ---
        r = api.get(f"/api/topics/{tid}/provider-config/effective")
        assert r.status_code == 200, r.text
        eff = r.json()
        assert eff["is_ready"], f"Not ready: {eff.get('missing_fields')}"

        # --- Run v2 preview ---
        r = api.post(
            f"/api/topics/{tid}/analysis/runs",
            json={
                "mode": "preview",
                "limit_chunks": 1,
                "requested_types": ["overview", "characters", "events"],
            },
        )
        assert r.status_code == 201, r.text
        rid = r.json()["run"]["id"]

        # --- Poll for completion ---
        start = time.monotonic()
        while time.monotonic() - start < MAX_WAIT:
            r = api.get(f"/api/analysis/runs/{rid}")
            assert r.status_code == 200, r.text
            status = r.json()
            state = status["run"]["status"]
            p = status["run"]
            if state in ("succeeded", "partial_success", "failed", "cancelled"):
                break
            time.sleep(POLL_INTERVAL)
        else:
            raise TimeoutError(f"Run {rid} did not complete within {MAX_WAIT}s")

        assert state == "succeeded", f"Run failed: {p.get('error_message', '')}"
        assert p["extraction_succeeded"] >= 1, "No extractions succeeded"
        assert p["total_tokens"] > 0, "No LLM tokens consumed"

        # --- Verify outputs ---
        r = api.get(f"/api/topics/{tid}/analysis/outputs?run_id={rid}")
        assert r.status_code == 200, r.text
        all_outputs = r.json()["outputs"]
        # Exclude merge intermediates
        final_outputs = [o for o in all_outputs if not o["output_type"].startswith("merge_")]
        assert len(final_outputs) >= 1, "No final outputs produced"

        for fo in final_outputs:
            cj = fo.get("content_json")
            if isinstance(cj, (dict, list)):
                content_len = len(str(cj))
            elif isinstance(cj, str):
                content_len = len(cj)
            else:
                content_len = 0
            assert content_len > 100, (
                f"Output {fo['output_type']} has no content ({content_len} chars)"
            )

    finally:
        api.delete(f"/api/topics/{tid}")


if __name__ == "__main__":
    print("Start the backend first:\n    uvicorn main:app --port 8000\n")
    print("Then run:\n    pytest tests/integration/test_v02_smoke.py -v -s -m integration\n")
