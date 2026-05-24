"""v0.2 integration smoke test — runs against a live backend with real LLM.

Start backend first:
    uvicorn main:app --port 8000
Then:
    python scripts/integration_smoke.py
"""

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

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
    "你天资聪颖，但性子急躁。修行之路，最忌讳的就是急躁。\"\n\n"
    '"大师教训得是。"张三低头道。\n\n'
    '"我不是什么大师，"李四笑了笑，"我只是个普通的读书人。'
    "不过你师父托付的事，我会尽力去做。\"\n\n"
    "从此，张三便在李四家中住了下来，开始了他在长安城的修行生涯。\n"
)


def check(desc, ok, detail=""):
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {desc}")
    if detail and not ok:
        print(f"         {detail}")
    return ok


def main():
    print("=== v0.2 Integration Smoke Test ===\n")
    passed = 0
    failed = 0

    client = httpx.Client(timeout=30, base_url=BASE)

    # ── Health ──
    r = client.get("/api/health")
    ok = r.status_code == 200 and r.json()["version"] == "0.2.0-dev"
    passed += check("Backend healthy", ok, r.text)
    if not ok:
        failed += 1
        return
    failed += 0

    # ── Provider ──
    r = client.get("/api/providers")
    providers = r.json()["providers"]
    ok = len(providers) > 0
    passed += check("Provider exists", ok, "Need at least one provider with real API key")
    if not ok:
        failed += 1
        client.close()
        return
    failed += 0
    pid = providers[0]["id"]
    print(f"         using: {providers[0]['name']} / {providers[0]['model_name']}")

    # ── Create topic ──
    name = f"smoke-{uuid.uuid4().hex[:6]}"
    r = client.post("/api/topics", json={"name": name, "provider_id": pid})
    ok = r.status_code == 201
    passed += check("Create topic", ok, r.text)
    failed += int(not ok)
    tid = r.json()["id"]

    try:
        # ── Upload ──
        r = client.post(
            f"/api/topics/{tid}/documents/upload",
            files={"file": ("smoke.txt", SAMPLE.encode("utf-8"), "text/plain")},
        )
        ok = r.status_code in (200, 201)
        passed += check("Upload document", ok, r.text)
        failed += int(not ok)
        doc = r.json()
        if ok:
            print(f"         {doc['char_count']} chars")

        # ── Parse ──
        r = client.post(f"/api/topics/{tid}/parse")
        ok = r.status_code == 200 and r.json()["chunk_count"] > 0
        passed += check("Parse document", ok, r.text)
        failed += int(not ok)
        parsed = r.json()
        if ok:
            print(f"         {parsed['chapter_count']} chapters, {parsed['chunk_count']} chunks")

        # ── Config ──
        r = client.get(f"/api/topics/{tid}/provider-config/effective")
        eff = r.json()
        ok = eff["is_ready"]
        passed += check("Config ready", ok, str(eff.get("missing_fields", [])))
        failed += int(not ok)

        # ── Run v2 preview ──
        r = client.post(
            f"/api/topics/{tid}/analysis/runs",
            json={
                "mode": "preview",
                "limit_chunks": min(3, parsed["chunk_count"]),
                "requested_types": ["overview", "characters", "events"],
            },
        )
        ok = r.status_code == 201
        passed += check("Create v2 run", ok, r.text)
        failed += int(not ok)
        rid = r.json()["run"]["id"]
        print(f"         run {rid[:8]}... limit={min(3, parsed['chunk_count'])}")

        # ── Poll for completion ──
        start = time.monotonic()
        state = "running"
        while time.monotonic() - start < MAX_WAIT:
            r = client.get(f"/api/analysis/runs/{rid}")
            status = r.json()
            state = status["run"]["status"]
            p = status["run"]
            print(f"         [{state}] {p['progress_current']}/{p['progress_total']} tok={p['total_tokens']}")
            if state in ("succeeded", "partial_success", "failed", "cancelled"):
                break
            time.sleep(POLL_INTERVAL)

        elapsed = time.monotonic() - start
        ok = state == "succeeded"
        passed += check(
            f"Analysis succeeded ({elapsed:.0f}s)",
            ok,
            f"status={state} error={status['run'].get('error_message', '')}",
        )
        failed += int(not ok)
        if ok:
            p = status["run"]
            print(f"         extractions: {p['extraction_succeeded']}/{p['extraction_total']}")
            print(f"         tokens: {p['total_tokens']}")

        # ── Verify outputs ──
        # Fetch outputs via the topic endpoint, filtered by run_id
        r = client.get(f"/api/topics/{tid}/analysis/outputs?run_id={rid}")
        outputs_data = r.json()
        all_outputs = outputs_data.get("outputs", [])
        # Exclude merge intermediates — only check final outputs
        final_outputs = [o for o in all_outputs if not o["output_type"].startswith("merge_")]
        print(f"\n         Final outputs: {len(final_outputs)}")

        for fo in final_outputs:
            cj = fo.get("content_json")
            if isinstance(cj, (dict, list)):
                content_len = len(str(cj))
            elif isinstance(cj, str):
                content_len = len(cj)
            else:
                content_len = 0

            ok = content_len > 100
            passed += check(
                f"  Output [{fo['output_type']}] {fo['title']}",
                ok,
                f"content_len={content_len}",
            )
            failed += int(not ok)
            if ok:
                print(f"             {content_len} chars")

        print(f"\n=== RESULTS: {passed} passed, {failed} failed ===")

    finally:
        client.delete(f"/api/topics/{tid}")
        print("Cleaned up.")
        client.close()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
