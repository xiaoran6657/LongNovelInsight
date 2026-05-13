# Smoke Test — LongNovelInsight Backend

## What is a smoke test?

A smoke test is a quick end-to-end check that exercises the full API flow against a **live running server**. Unlike `pytest` unit tests (which use mock LLM responses and an in-memory database), the smoke test sends real HTTP requests to a running FastAPI backend and verifies that all endpoints work together.

| | pytest | smoke_backend.py |
|---|---|---|
| Database | In-memory SQLite per test | Real `data/longnovelinsight.sqlite` |
| LLM calls | Mocked | Real (only with `--real-llm`) |
| Server | TestClient (no network) | Live HTTP via httpx |
| Purpose | Catch regressions in code | Catch integration / deployment issues |

## Prerequisites

1. Start the backend server:

```bash
cd backend
conda activate LongNovelInsight
python -m uvicorn main:app --reload --port 8000
```

2. Verify the server is running:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected: `{"status":"ok","version":"0.1.0","topic_count":0,"total_disk_usage_bytes":...}`

## Running the safe-mode smoke test (no real LLM)

Default safe mode uses a fake provider with placeholder credentials. No external API calls are made.

```bash
cd backend
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup
```

This tests:
1. `GET /api/health`
2. `POST /api/model-providers` (fake credentials)
3. `POST /api/topics`
4. `POST /api/topics/{id}/documents/upload`
5. `GET /api/topics/{id}/documents/current`
6. `POST /api/topics/{id}/parse`
7. `GET /api/topics/{id}/chapters`
8. `GET /api/topics/{id}/chunks?include_text=true`
9. `GET /api/topics/{id}/storage`
10. `POST /api/topics/{id}/analysis/jobs`
11. `GET /api/topics/{id}/analysis/status`
12. `GET /api/analysis/jobs/{id}`
13. `POST /api/topics/{id}/chat/sessions`
14. `GET /api/topics/{id}/chat/sessions`
15. `GET /api/chat/sessions/{id}/messages`
16. Cleanup (delete session, topic, provider)

## Running the real-LLM smoke test

**WARNING: This mode calls your LLM provider and consumes API quota.**

1. Set your API key as an environment variable:

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"

# Linux / macOS / Git Bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

2. Run with `--real-llm`:

```bash
cd backend
python scripts/smoke_backend.py \
    --base-url http://127.0.0.1:8000 \
    --real-llm \
    --provider-name DeepSeek \
    --provider-base-url https://api.deepseek.com \
    --provider-model deepseek-chat \
    --provider-api-key-env DEEPSEEK_API_KEY \
    --cleanup
```

Additional steps (beyond safe mode):
- `POST /api/model-providers/{id}/test` — connection test
- `POST /api/topics/{id}/analysis/run?limit_chunks=2` — real structured analysis
- `GET /api/topics/{id}/analysis/outputs` — verify analysis results
- `POST /api/chat/sessions/{id}/messages` — real chat with evidence

## Common failure reasons

| Symptom | Likely cause |
|---------|-------------|
| Connection refused | Backend is not running (`uvicorn main:app --port 8000`) |
| Wrong port | Backend is on a different port; use `--base-url` |
| 400 / 500 on parse/upload | Old SQLite database with incompatible schema. Delete `data/longnovelinsight.sqlite` and restart. |
| Provider test failed (real mode) | Wrong API key or `provider_api_key_env` not set |
| 401 from provider (real mode) | Invalid API key |
| JSON parse error in response | API response format changed — check `docs/API.md` against current code |

## Data safety

- Smoke test data is written to the live `data/longnovelinsight.sqlite` and `data/topics/` directory.
- Running with `--cleanup` deletes created resources via the API.
- If `--cleanup` is omitted, a provider and topic named `smoke-test-*` will remain in the database.
- Do NOT commit smoke-test data to Git (these files are in `.gitignore`).

## Script options

```
--base-url URL            Base URL (default: http://127.0.0.1:8000)
--cleanup                 Delete created resources after test
--real-llm                Use real LLM provider (consumes API quota)
--provider-name NAME      Provider display name
--provider-base-url URL   Provider API base URL
--provider-model MODEL    Model name
--provider-api-key-env ENV Environment variable for API key (default: DEEPSEEK_API_KEY)
--timeout SECONDS         HTTP request timeout (default: 60)
```
