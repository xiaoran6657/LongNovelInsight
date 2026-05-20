#!/usr/bin/env python3
"""v0.2 Backend smoke test — v2 analysis pipeline API verification.

Default (safe) mode verifies the full v2 API surface without calling a real LLM:
creates a run, polls status, lists runs, and cleans up. No API key consumed.

Use --real-llm to actually execute a v2 run against a live provider (consumes API quota).

Usage:
  # Safe mode (no real API calls):
  python scripts/smoke_v2_backend.py --base-url http://127.0.0.1:8000 --cleanup

  # Real LLM mode (consumes API quota):
  set DEEPSEEK_API_KEY=sk-...
  python scripts/smoke_v2_backend.py --real-llm --provider-api-key-env DEEPSEEK_API_KEY
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import httpx

_step = 0
_total = 14
_provider_api_key = ""


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:3] + "..." + key[-4:]


def _safe_body(data: dict | list | None) -> str:
    if data is None:
        return "(no body)"
    s = repr(data)
    if _provider_api_key:
        s = s.replace(_provider_api_key, _mask_key(_provider_api_key))
    if len(s) > 500:
        s = s[:500] + "...(truncated)"
    return s


def _step_header(title: str) -> None:
    global _step
    _step += 1
    print(f"[{_step}/{_total}] {title}")


def _fail(client: httpx.Client, method: str, url: str, resp: httpx.Response) -> None:
    body = None
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]
    print(f"  FAILED: {method} {url}")
    print(f"  Status: {resp.status_code}")
    print(f"  Body: {_safe_body(body)}")
    client.close()
    sys.exit(1)


def _get_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


# ── Steps ──


def _health(client: httpx.Client, base: str) -> None:
    _step_header("Health check")
    url = f"{base}/api/health"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and data.get("status") == "ok"
    print(f"  OK — status={data['status']}")


def _create_provider(client: httpx.Client, base: str, real_llm: bool = False) -> str:
    _step_header("Create ModelProvider")
    url = f"{base}/api/providers"
    if real_llm:
        body = {
            "name": "smoke-v2-provider",
            "provider_type": "openai_compatible",
            "base_url": os.environ.get("SMOKE_PROVIDER_URL", "https://api.deepseek.com"),
            "api_key": _provider_api_key,
            "model_name": os.environ.get("SMOKE_MODEL_NAME", "deepseek-chat"),
            "is_default": True,
        }
    else:
        body = {
            "name": "smoke-v2-safe-provider",
            "provider_type": "openai_compatible",
            "base_url": "https://fake.example.com",
            "api_key": "sk-fake-smoke-test",
            "model_name": "fake-model",
            "is_default": True,
        }
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "id" in data
    print(f"  OK — provider_id={data['id']}")
    return data["id"]


def _create_topic(client: httpx.Client, base: str, provider_id: str) -> str:
    _step_header("Create Topic")
    url = f"{base}/api/topics"
    body = {"name": "smoke-v2-topic", "provider_id": provider_id}
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    tid = _get_json(resp)["id"]
    print(f"  OK — topic_id={tid}")
    return tid


def _bind_provider_config(client: httpx.Client, base: str, topic_id: str, provider_id: str) -> None:
    _step_header("Bind provider config")
    url = f"{base}/api/topics/{topic_id}/provider-config"
    body = {"provider_id": provider_id}
    resp = client.put(url, json=body)
    if resp.status_code != 200:
        _fail(client, "PUT", url, resp)
    print("  OK — provider config bound")


def _upload(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("Upload .txt document")
    url = f"{base}/api/topics/{topic_id}/documents/upload"
    content = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。\n"
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}
    resp = client.post(url, files=files)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    print("  OK — document uploaded")


def _parse(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("Parse document")
    url = f"{base}/api/topics/{topic_id}/parse"
    resp = client.post(url)
    if resp.status_code != 200:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    print(f"  OK — chapters={data['chapter_count']} chunks={data['chunk_count']}")


def _chunks_meta(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET chunks/meta")
    url = f"{base}/api/topics/{topic_id}/chunks/meta"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and data.get("chunk_count", 0) >= 1
    print(f"  OK — chunk_count={data['chunk_count']} total_chars={data.get('total_chars')}")


def _create_v2_run(client: httpx.Client, base: str, topic_id: str, real_llm: bool = False) -> str:
    mode_label = "real-LLM" if real_llm else "safe"
    _step_header(f"Create v2 AnalysisRun ({mode_label} mode)")
    url = f"{base}/api/topics/{topic_id}/analysis/runs"
    body = {
        "mode": "preview",
        "limit_chunks": 1,
        "requested_types": ["overview", "characters"],
        "start_immediately": real_llm,
    }
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "run" in data
    rid = data["run"]["id"]
    st = data["run"]["status"]
    pt = data["run"]["progress_total"]
    print(f"  OK — run_id={rid} status={st} progress_total={pt}")
    return rid


def _poll_run_status(client: httpx.Client, base: str, run_id: str, real_llm: bool = False) -> None:
    _step_header("Poll run status")
    url = f"{base}/api/analysis/runs/{run_id}"
    for _ in range(30 if real_llm else 3):
        resp = client.get(url)
        if resp.status_code != 200:
            _fail(client, "GET", url, resp)
        data = _get_json(resp)
        status = data["run"]["status"]
        if status in ("succeeded", "partial_success", "failed", "cancelled"):
            es = data["run"]["extraction_succeeded"]
            ef = data["run"]["extraction_failed"]
            ms = data["run"]["merge_succeeded"]
            fs = data["run"]["final_succeeded"]
            print(f"  OK — status={status} extraction={es}/{ef}")
            print(f"       merge_succeeded={ms} final_succeeded={fs}")
            return
        time.sleep(2)
    # In safe mode, the run stays pending (start_immediately=false)
    if not real_llm:
        print("  OK — run is pending (safe mode, start_immediately=false)")
    else:
        print("  WARNING — run did not complete in 60s")


def _list_runs(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("List analysis runs")
    url = f"{base}/api/topics/{topic_id}/analysis/runs"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    runs = data.get("runs", [])
    assert len(runs) >= 1
    print(f"  OK — {len(runs)} runs found")


def _get_outputs(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET analysis outputs")
    url = f"{base}/api/topics/{topic_id}/analysis/outputs"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    print(f"  OK — {data['count']} outputs (may be 0 in safe mode)")


def _get_legacy_status(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET legacy analysis/status")
    url = f"{base}/api/topics/{topic_id}/analysis/status"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict)
    assert "v2_available" in data
    assert data.get("v2_available") is True
    has_run = "present" if data.get("latest_v2_run") else "none"
    print(f"  OK — v2_available={data['v2_available']} latest_v2_run={has_run}")


def _cleanup_provider(client: httpx.Client, base: str, provider_id: str) -> None:
    _step_header("Cleanup provider")
    url = f"{base}/api/providers/{provider_id}"
    resp = client.delete(url)
    if resp.status_code == 409:
        print("  SKIP — provider still in use by topic")
    elif resp.status_code == 200:
        print("  OK — provider deleted")
    else:
        _fail(client, "DELETE", url, resp)


def _cleanup_topic(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("Cleanup topic")
    url = f"{base}/api/topics/{topic_id}"
    resp = client.delete(url)
    if resp.status_code != 200:
        _fail(client, "DELETE", url, resp)
    print("  OK — topic deleted")


# ── Main ──


def main() -> None:
    global _provider_api_key, _total

    parser = argparse.ArgumentParser(description="v0.2 Backend smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--real-llm", action="store_true", help="Use real LLM (consumes API quota)")
    parser.add_argument("--provider-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument(
        "--cleanup", action="store_true", help="Delete created resources after test"
    )
    args = parser.parse_args()

    if args.real_llm:
        _provider_api_key = os.environ.get(args.provider_api_key_env, "")
        if not _provider_api_key:
            print(f"ERROR: --real-llm requires {args.provider_api_key_env} to be set")
            sys.exit(1)
        _total = 15
    else:
        _total = 14

    base = args.base_url.rstrip("/")
    client = httpx.Client(timeout=30.0)

    print("v0.2 Backend Smoke Test")
    print(f"Base URL: {base}")
    print(f"Mode: {'real-LLM' if args.real_llm else 'safe (no real API calls)'}")
    print()

    try:
        _health(client, base)

        provider_id = _create_provider(client, base, real_llm=args.real_llm)
        tid = _create_topic(client, base, provider_id)
        _bind_provider_config(client, base, tid, provider_id)
        _upload(client, base, tid)
        _parse(client, base, tid)
        _chunks_meta(client, base, tid)

        rid = _create_v2_run(client, base, tid, real_llm=args.real_llm)
        _poll_run_status(client, base, rid, real_llm=args.real_llm)
        _list_runs(client, base, tid)
        _get_outputs(client, base, tid)
        _get_legacy_status(client, base, tid)

        if args.real_llm:
            _step_header("Wait for run completion")
            url = f"{base}/api/analysis/runs/{rid}"
            for _ in range(60):
                resp = client.get(url)
                data = _get_json(resp)
                if data["run"]["status"] in ("succeeded", "partial_success", "failed"):
                    print(f"  FINAL — status={data['run']['status']}")
                    break
                time.sleep(3)
            else:
                print("  WARNING — run did not complete in 180s")

    finally:
        if args.cleanup:
            print()
            _cleanup_topic(client, base, tid)
            _cleanup_provider(client, base, provider_id)

        client.close()

    print()
    print("v0.2 smoke test complete.")


if __name__ == "__main__":
    main()
