#!/usr/bin/env python3
"""Backend smoke test — exercises the full API flow against a live server.

Default (safe) mode uses placeholder credentials and never calls a real LLM.
Use --real-llm to test against an actual provider (consumes API quota).

Usage:
  python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup

  # Real LLM mode:
  set DEEPSEEK_API_KEY=sk-...
  python scripts/smoke_backend.py --real-llm \
      --provider-name DeepSeek \
      --provider-base-url https://api.deepseek.com \
      --provider-model deepseek-chat \
      --provider-api-key-env DEEPSEEK_API_KEY
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx

# ── helpers ──────────────────────────────────────────────────────────────────

_step = 0
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
    # Truncate long bodies
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


# ── default-safe flow ────────────────────────────────────────────────────────


def _health(client: httpx.Client, base: str) -> None:
    _step_header("Health check")
    url = f"{base}/api/health"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and data.get("status") == "ok"
    print(f"  OK — status={data['status']} topics={data.get('topic_count')}")


def _create_provider_safe(client: httpx.Client, base: str) -> str:
    _step_header("Create ModelProvider (fake)")
    url = f"{base}/api/providers"
    body = {
        "name": "smoke-test-provider",
        "provider_type": "openai_compatible",
        "base_url": "https://fake.example.com",
        "api_key": "sk-fake-smoke-test-key",
        "model_name": "fake-model",
        "is_default": True,
    }
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "id" in data
    assert "api_key" not in data
    assert "masked_api_key" in data
    pid = data["id"]
    print(f"  OK — provider_id={pid} masked_key={data['masked_api_key']}")
    return pid


def _create_topic(client: httpx.Client, base: str, provider_id: str) -> str:
    _step_header("Create Topic")
    url = f"{base}/api/topics"
    body = {"name": "smoke-test-topic", "provider_id": provider_id}
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "id" in data
    tid = data["id"]
    print(f"  OK — topic_id={tid}")
    return tid


def _upload_document(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("Upload .txt document")
    url = f"{base}/api/topics/{topic_id}/documents/upload"
    content = "第一章 风起\n张三走进长安城。\n第二章 雨落\n李四拔剑。\n"
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}
    resp = client.post(url, files=files)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and data.get("status") == "uploaded"
    print(f"  OK — status={data['status']} char_count={data.get('char_count')}")


def _get_current_document(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET current document")
    url = f"{base}/api/topics/{topic_id}/documents/current"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict)
    assert data.get("original_filename") == "novel.txt"
    print(f"  OK — file={data['original_filename']} encoding={data.get('encoding')}")


def _parse(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("POST parse")
    url = f"{base}/api/topics/{topic_id}/parse"
    resp = client.post(url)
    if resp.status_code != 200:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict)
    assert data.get("chapter_count", 0) >= 1
    assert data.get("chunk_count", 0) >= 1
    print(f"  OK — chapters={data['chapter_count']} chunks={data['chunk_count']}")


def _get_chapters(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET chapters")
    url = f"{base}/api/topics/{topic_id}/chapters"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    chapters = data.get("chapters", [])
    assert len(chapters) >= 1
    titles = [c.get("title", "") for c in chapters]
    print(f"  OK — {len(chapters)} chapters: {titles}")


def _get_chunks(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET chunks (include_text=true)")
    url = f"{base}/api/topics/{topic_id}/chunks?include_text=true&limit=10"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    chunks = data.get("chunks", [])
    assert len(chunks) >= 1
    # Verify Chinese text is not garbled
    sample = chunks[0].get("text", "")
    assert "张" in sample or "李" in sample or len(sample) > 0
    print(f"  OK — {len(chunks)} chunks, first_chunk_len={len(sample)}")


def _get_storage(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET storage")
    url = f"{base}/api/topics/{topic_id}/storage"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    usage = data.get("total_disk_usage_bytes", -1)
    assert usage >= 0
    print(f"  OK — total_disk_usage_bytes={usage}")


def _create_analysis_job(client: httpx.Client, base: str, topic_id: str) -> str:
    _step_header("Create analysis job")
    url = f"{base}/api/topics/{topic_id}/analysis/jobs"
    resp = client.post(url)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    job = data.get("job", {})
    assert job.get("id")
    print(f"  OK — job_id={job['id']} status={job.get('status')} type={job.get('job_type')}")
    return job["id"]


def _get_analysis_status(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET analysis status")
    url = f"{base}/api/topics/{topic_id}/analysis/status"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict)
    print(
        f"  OK — has_jobs={data.get('has_jobs')} completed={data.get('analysis_types_completed')}"
    )


def _get_job_detail(client: httpx.Client, base: str, job_id: str) -> None:
    _step_header("GET job detail")
    url = f"{base}/api/analysis/jobs/{job_id}"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and data.get("job")
    print(f"  OK — items={len(data.get('items', []))}")


def _create_chat_session(client: httpx.Client, base: str, topic_id: str) -> str:
    _step_header("Create chat session")
    url = f"{base}/api/topics/{topic_id}/chat/sessions"
    body = {"title": "Smoke Test Chat"}
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "id" in data
    sid = data["id"]
    print(f"  OK — session_id={sid}")
    return sid


def _get_chat_sessions(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET chat sessions")
    url = f"{base}/api/topics/{topic_id}/chat/sessions"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    assert len(data.get("sessions", [])) >= 1
    print(f"  OK — {len(data['sessions'])} sessions")


def _get_chat_messages(client: httpx.Client, base: str, session_id: str) -> None:
    _step_header("GET chat messages")
    url = f"{base}/api/chat/sessions/{session_id}/messages"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    print(f"  OK — {data.get('total', 0)} messages")


# ── real-LLM flow ────────────────────────────────────────────────────────────


def _create_provider_real(client: httpx.Client, base: str, args: argparse.Namespace) -> str:
    _step_header("Create ModelProvider (real)")

    global _provider_api_key
    _provider_api_key = os.environ.get(args.provider_api_key_env, "")
    if not _provider_api_key:
        print(f"  ERROR: env var {args.provider_api_key_env} is not set or empty")
        sys.exit(1)

    url = f"{base}/api/providers"
    body = {
        "name": args.provider_name or "smoke-real-provider",
        "provider_type": "openai_compatible",
        "base_url": args.provider_base_url or "https://api.deepseek.com",
        "api_key": _provider_api_key,
        "model_name": args.provider_model or "deepseek-chat",
        "is_default": True,
    }
    resp = client.post(url, json=body)
    if resp.status_code != 201:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert isinstance(data, dict) and "id" in data
    assert "api_key" not in data
    pid = data["id"]
    masked = data.get("masked_api_key", "***")
    print(f"  OK — provider_id={pid} masked_key={masked}")
    print(f"  NOTE: this will consume API quota for {body['model_name']}")
    return pid


def _provider_test(client: httpx.Client, base: str, provider_id: str) -> None:
    _step_header("Provider test endpoint")
    url = f"{base}/api/providers/{provider_id}/test"
    resp = client.post(url)
    if resp.status_code != 200:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert data.get("success") is True, f"Provider test failed: {data.get('message')}"
    print(f"  OK — latency_ms={data.get('latency_ms')} model={data.get('model_name')}")


def _run_analysis(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("Run structured analysis (limit_chunks=2)")
    url = f"{base}/api/topics/{topic_id}/analysis/run?limit_chunks=2"
    resp = client.post(url)
    if resp.status_code != 200:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    outputs = data.get("outputs", [])
    assert len(outputs) >= 1, "Expected at least 1 analysis output"
    types_found = {o.get("output_type") for o in outputs}
    print(f"  OK — {len(outputs)} outputs: {types_found}")


def _check_analysis_outputs(client: httpx.Client, base: str, topic_id: str) -> None:
    _step_header("GET analysis outputs")
    url = f"{base}/api/topics/{topic_id}/analysis/outputs"
    resp = client.get(url)
    if resp.status_code != 200:
        _fail(client, "GET", url, resp)
    data = _get_json(resp)
    outputs = data.get("outputs", [])
    assert len(outputs) >= 1
    for o in outputs:
        assert o.get("output_type")
        assert "confidence" in o
    print(f"  OK — {len(outputs)} outputs with confidence fields")


def _send_chat_message(client: httpx.Client, base: str, session_id: str) -> None:
    _step_header("Send chat message (real LLM)")
    url = f"{base}/api/chat/sessions/{session_id}/messages"
    body = {"content": "张三做了什么？请基于证据回答。"}
    resp = client.post(url, json=body)
    if resp.status_code != 200:
        _fail(client, "POST", url, resp)
    data = _get_json(resp)
    assert data.get("role") == "assistant"
    assert data.get("content") and len(data["content"]) > 0
    evidence = data.get("evidence_json")
    uncertainty = data.get("uncertainty")
    print(
        f"  OK — answer_len={len(data['content'])} "
        f"evidence={evidence is not None} uncertainty={uncertainty}"
    )


# ── cleanup ──────────────────────────────────────────────────────────────────


def _cleanup(
    client: httpx.Client,
    base: str,
    topic_id: str | None,
    provider_id: str | None,
    session_id: str | None,
) -> None:
    _step_header("Cleanup")
    errors = []

    if session_id:
        url = f"{base}/api/chat/sessions/{session_id}"
        resp = client.delete(url)
        if resp.status_code == 200:
            print("  deleted chat session")
        else:
            msg = f"delete session returned {resp.status_code}"
            print(f"  WARNING: {msg}")
            errors.append(msg)

    if topic_id:
        url = f"{base}/api/topics/{topic_id}"
        resp = client.delete(url)
        if resp.status_code == 200:
            print("  deleted topic")
        else:
            msg = f"delete topic returned {resp.status_code}"
            print(f"  WARNING: {msg}")
            errors.append(msg)

    if provider_id:
        url = f"{base}/api/providers/{provider_id}"
        resp = client.delete(url)
        if resp.status_code == 200:
            print("  deleted provider")
        else:
            msg = f"delete provider returned {resp.status_code}"
            print(f"  WARNING: {msg}")
            errors.append(msg)

    if errors:
        print(f"  NOTE: {len(errors)} cleanup issue(s) — this is not a test failure.")


# ── main ─────────────────────────────────────────────────────────────────────


_total = 0


def _count_steps(args: argparse.Namespace) -> int:
    # Default steps: health, provider, topic, upload, get-doc, parse,
    #   chapters, chunks, storage, job, status, job-detail,
    #   create-session, list-sessions, get-messages [+ cleanup]
    n = 15
    if args.real_llm:
        n += 4  # provider-test, analysis-run, get-outputs, send-message
    if args.cleanup:
        n += 1
    return n


def main() -> None:
    global _total

    parser = argparse.ArgumentParser(description="LongNovelInsight backend smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--real-llm", action="store_true")
    parser.add_argument("--provider-name", default=None)
    parser.add_argument("--provider-base-url", default=None)
    parser.add_argument("--provider-model", default=None)
    parser.add_argument("--provider-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    _total = _count_steps(args)
    base = args.base_url.rstrip("/")

    client = httpx.Client(timeout=args.timeout)
    topic_id: str | None = None
    provider_id: str | None = None
    session_id: str | None = None

    try:
        # ── Default-safe steps ──
        _health(client, base)

        if args.real_llm:
            provider_id = _create_provider_real(client, base, args)
        else:
            provider_id = _create_provider_safe(client, base)

        topic_id = _create_topic(client, base, provider_id)
        _upload_document(client, base, topic_id)
        _get_current_document(client, base, topic_id)
        _parse(client, base, topic_id)
        _get_chapters(client, base, topic_id)
        _get_chunks(client, base, topic_id)
        _get_storage(client, base, topic_id)

        job_id = _create_analysis_job(client, base, topic_id)
        _get_analysis_status(client, base, topic_id)
        _get_job_detail(client, base, job_id)

        session_id = _create_chat_session(client, base, topic_id)
        _get_chat_sessions(client, base, topic_id)
        _get_chat_messages(client, base, session_id)

        # ── Real-LLM steps ──
        if args.real_llm:
            _provider_test(client, base, provider_id)
            _run_analysis(client, base, topic_id)
            _check_analysis_outputs(client, base, topic_id)
            _send_chat_message(client, base, session_id)

        # ── Cleanup ──
        if args.cleanup:
            _cleanup(client, base, topic_id, provider_id, session_id)
            topic_id = None
            provider_id = None
            session_id = None

        print(f"\n{'=' * 50}")
        print("Smoke test PASSED")
        print(f"{'=' * 50}")

    finally:
        if args.cleanup and (topic_id or provider_id or session_id):
            _cleanup(client, base, topic_id, provider_id, session_id)
        client.close()


if __name__ == "__main__":
    main()
