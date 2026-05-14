# Frontend API Contract — LongNovelInsight v0.1.0

> Auto-generated from actual backend code (routers/ + models/), not from docs/API.md alone.
> If a discrepancy is found between this document and backend behavior, the backend code is the authority.

## 1. Base URL & Environment

| Item | Value |
|------|-------|
| Default backend URL | `http://127.0.0.1:8000` |
| Frontend env var | `VITE_API_BASE_URL=http://127.0.0.1:8000` |
| API prefix | `/api` |
| CORS allowed origin | `http://localhost:5173` (configured in `backend/main.py`) |
| CORS methods | `*` (all) |
| CORS headers | `*` (all) |

**CORS status:** ✅ Already configured. If frontend runs on `http://127.0.0.1:5173`, add it to `allow_origins` in `backend/main.py` as well (`"http://127.0.0.1:5173"`).

## 2. Status Values (All Lowercase)

### Topic Status
| Value | Meaning |
|-------|---------|
| `created` | Topic just created |
| `uploaded` | Document uploaded |
| `parsed` | Document parsed into chapters/chunks |
| `analyzing` | Analysis in progress |
| `ready` | Analysis complete |
| `failed` | Error state |

### Document Status
| Value | Meaning |
|-------|---------|
| `uploaded` | File received and saved |
| `parsing` | Parse in progress |
| `parsed` | Parse complete |
| `failed` | Parse error |

### Job Status
| Value | Meaning |
|-------|---------|
| `pending` | Job created, not started |
| `running` | Job in progress |
| `succeeded` | All items completed |
| `failed` | One or more items failed |
| `cancelled` | Cancelled by user |

### Analysis Type (output_type / item_type)
| Value | LLM Prompt File |
|-------|----------------|
| `overview` | `prompts/overview.md` |
| `characters` | `prompts/characters.md` |
| `relations` | `prompts/relations.md` |
| `events` | `prompts/events.md` |
| `causality` | `prompts/causality.md` |
| `themes` | `prompts/themes.md` |

### Job Type
| Value | Meaning |
|-------|---------|
| `parse` | Parse job (stub, no LLM) |
| `analysis` | Analysis job (real LLM calls) |

## 3. API Endpoints

### 3.1 Health

**`GET /api/health`**

Response `200`:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "topic_count": 3,
  "total_disk_usage_bytes": 5242880
}
```
Frontend use: Display connection status, version, topic count on Dashboard.

---

### 3.2 Providers (`/api/providers`)

**`GET /api/providers`**

Response `200`:
```json
{
  "providers": [
    {
      "id": "uuid",
      "name": "My DeepSeek",
      "provider_type": "openai_compatible",
      "base_url": "https://api.deepseek.com",
      "model_name": "deepseek-chat",
      "context_window": 1000000,
      "max_output_tokens": 8192,
      "temperature": 0.2,
      "is_default": true,
      "masked_api_key": "sk-...abcd",
      "created_at": "2026-05-10T12:00:00Z",
      "updated_at": "2026-05-10T12:00:00Z"
    }
  ]
}
```
⚠️ `api_key` is NEVER returned. Only `masked_api_key`.

**`POST /api/providers`** (201)

Request:
```json
{
  "name": "My DeepSeek",
  "provider_type": "openai_compatible",
  "base_url": "https://api.deepseek.com",
  "api_key": "sk-...",
  "model_name": "deepseek-chat",
  "context_window": 1000000,
  "max_output_tokens": 8192,
  "temperature": 0.2,
  "is_default": true
}
```
Response `201`: Same shape as GET single provider.
Errors: `422` (validation: name empty, provider_type ≠ openai_compatible, base_url empty, api_key empty, model_name empty, temperature not in [0,2], context_window ≤ 0, max_output_tokens ≤ 0), `409` (name duplicate).

**`GET /api/providers/{provider_id}`**

Response `200`: Single provider object. `404` if not found.

**`PATCH /api/providers/{provider_id}`**

Request: Any subset of provider fields (all optional).
Response `200`: Updated provider object.
Errors: `404` not found, `409` name conflict, `422` invalid provider_type.

**`DELETE /api/providers/{provider_id}`**

Response `200`: `{ "deleted": true }`
Errors: `404` not found, `409` in use by a Topic.

**`POST /api/providers/{provider_id}/test`**

Response `200`:
```json
{
  "success": true,
  "provider_id": "uuid",
  "model_name": "deepseek-chat",
  "latency_ms": 450,
  "message": "Connection successful"
}
```
On failure: `200` with `"success": false` and error message (api_key sanitized). `404` provider not found.

⚠️ This endpoint makes a real API call to the LLM provider. Show warning in UI.

---

### 3.3 Topics

**`GET /api/topics`**

Response `200`:
```json
{
  "topics": [
    {
      "id": "uuid",
      "name": "Three Kingdoms",
      "description": "...",
      "provider_id": "uuid or null",
      "storage_bytes": 1048576,
      "status": "created",
      "document": {
        "id": "uuid",
        "original_filename": "novel.txt",
        "status": "parsed",
        "file_size_bytes": 1048576,
        "char_count": 500000
      },
      "analysis_summary": {
        "overview": "completed",
        "characters": "completed"
      },
      "disk_usage_bytes": 1048576,
      "created_at": "2026-05-10T12:00:00Z",
      "updated_at": "2026-05-10T12:00:00Z"
    }
  ]
}
```
Note: `document` is `null` if no document uploaded. `analysis_summary` is `{}` if no analysis run. Keys in `analysis_summary` are AnalysisType values (`overview`, `characters`, etc.), values are `"completed"`.

**`POST /api/topics`** (201)

Request:
```json
{
  "name": "My Analysis",
  "description": "Optional description",
  "provider_id": "uuid or null"
}
```
Response `201`: Full topic object (same shape as list item).
Errors: `404` if provider_id given but not found.

**`GET /api/topics/{topic_id}`**

Response `200`: Full topic detail (same shape as list item, with real document/analysis_summary).
Errors: `404`.

**`DELETE /api/topics/{topic_id}`**

Response `200`: `{ "deleted": true, "freed_bytes": 1048576 }`
Errors: `404`.
⚠️ Full cascade: deletes document, chapters, chunks, analysis outputs, chat sessions + messages, jobs + items, and `data/topics/{id}/` directory.

---

### 3.4 Documents

**`POST /api/topics/{topic_id}/documents/upload`** (201)

Request: `multipart/form-data` with field `file` (`.txt` only, max 200MB).
Accepts: UTF-8, UTF-8-SIG, GB18030, GBK, GB2312, UTF-16. All normalized to UTF-8.

Response `201`:
```json
{
  "id": "uuid",
  "topic_id": "uuid",
  "original_filename": "novel.txt",
  "stored_filename": "original.txt",
  "file_type": "txt",
  "content_type": "text/plain",
  "encoding": "gbk",
  "file_size_bytes": 1048576,
  "char_count": 500000,
  "storage_path": "topics/{topic_id}/source/original.txt",
  "status": "uploaded",
  "created_at": "...",
  "updated_at": "..."
}
```
Errors: `404` topic not found, `400` not .txt, `400` unsupported encoding, `409` already has document, `413` file too large, `422` empty/whitespace-only file.

**`GET /api/topics/{topic_id}/documents/current`**

Response `200`: Full document object.
Errors: `404` topic not found, `404` no document.

**`DELETE /api/topics/{topic_id}/documents/current`**

Response `200`: `{ "deleted": true, "freed_bytes": 1048576 }`
Errors: `404` topic not found, `404` no document.
⚠️ Cascades: deletes all derived data (chapters, chunks, analysis outputs, chat, jobs).

---

### 3.5 Parse / Chapters / Chunks / Storage

**`POST /api/topics/{topic_id}/parse`**

Response `200`:
```json
{
  "chapter_count": 120,
  "chunk_count": 480,
  "char_count": 800000,
  "estimated_tokens": 533333
}
```
Errors: `404` topic not found, `404` no document, `409` original.txt not found on disk.

**`GET /api/topics/{topic_id}/chapters`**

Response `200`:
```json
{
  "chapters": [
    {
      "id": "uuid",
      "topic_id": "uuid",
      "document_id": "uuid",
      "chapter_index": 0,
      "title": "第一章 宴桃园豪杰三结义",
      "start_char": 0,
      "end_char": 6500,
      "char_count": 6500,
      "created_at": "..."
    }
  ]
}
```

**`GET /api/topics/{topic_id}/chunks?include_text=true&limit=100&offset=0`**

Response `200`:
```json
{
  "chunks": [
    {
      "id": "uuid",
      "chapter_index": 0,
      "chunk_index": 0,
      "text": "",
      "start_char": 0,
      "end_char": 4000,
      "char_count": 4000,
      "estimated_tokens": 2667
    }
  ]
}
```
Query params: `include_text` (bool, default `false`), `limit` (int, default `100`, max `1000`), `offset` (int, default `0`).
⚠️ Frontend should default to `include_text=false`. Only load text for preview of first ~20 chunks.

**`GET /api/topics/{topic_id}/storage`**

Response `200`:
```json
{
  "total_disk_usage_bytes": 5242880,
  "database_size_bytes": 204800,
  "data_dir_size_bytes": 5038080,
  "topics": [
    {
      "topic_id": "uuid",
      "topic_name": "Three Kingdoms",
      "novel_size_bytes": 1048576,
      "chunks_size_bytes": 480000,
      "analyses_size_bytes": 512000,
      "total_bytes": 2032576
    }
  ]
}
```

---

### 3.6 Analysis Outputs

**`POST /api/topics/{topic_id}/analysis/run?limit_chunks=5`**

Runs all 6 analysis types synchronously. Deletes old outputs before running.
⚠️ Makes real LLM calls. Show API consumption warning in UI.

Response `200`:
```json
{
  "outputs": [
    {
      "id": "uuid",
      "topic_id": "uuid",
      "job_id": null,
      "output_type": "overview",
      "title": "Work Overview",
      "content_json": { ... },
      "source_chunk_ids": ["uuid1", "uuid2"],
      "evidence_quotes": ["quote1", "quote2"],
      "confidence": 0.85,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "count": 6
}
```
Errors: `404` topic not found, `409` no document / not parsed / no provider.

**`GET /api/topics/{topic_id}/analysis/outputs?output_type=characters`**

Response `200`: `{ "outputs": [...], "count": N }`
Errors: `404` topic not found.
Query: `output_type` (optional) — filter by AnalysisType value.

**`DELETE /api/topics/{topic_id}/analysis/outputs`**

Response `200`: `{ "deleted": true, "count": N }`
Errors: `404` topic not found.

---

### 3.7 Analysis Jobs (internal API)

**`POST /api/topics/{topic_id}/analysis/jobs?job_type=analysis`** (201)

Valid `job_type`: `parse`, `analysis` (default: `analysis`).

Response `201`:
```json
{
  "job": {
    "id": "uuid",
    "topic_id": "uuid",
    "job_type": "analysis",
    "status": "succeeded",
    "progress_current": 6,
    "progress_total": 6,
    "message": "Analysis complete",
    "error_message": null,
    "started_at": "...",
    "finished_at": "...",
    "created_at": "...",
    "updated_at": "..."
  },
  "items": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "item_type": "overview",
      "status": "succeeded",
      "progress_current": 1,
      "progress_total": 1,
      "message": "overview completed",
      "error_message": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```
Errors: `404` topic not found, `409` no document / not parsed, `422` invalid job_type.

**`GET /api/topics/{topic_id}/analysis/jobs`**

Response `200`: `{ "jobs": [...] }`

**`GET /api/topics/{topic_id}/analysis/status`**

Response `200`:
```json
{
  "topic_id": "uuid",
  "has_jobs": true,
  "latest_job": { ... },
  "analysis_types_completed": ["overview", "characters"]
}
```
`analysis_types_completed` uses lowercase AnalysisType values.

**`GET /api/analysis/jobs/{job_id}`**

Response `200`: `{ "job": {...}, "items": [...] }`
Errors: `404`.

**`POST /api/analysis/jobs/{job_id}/cancel`**

Response `200`: `{ "job": {...}, "items": [...] }`
Errors: `404`.

---

### 3.8 Chat

**`POST /api/topics/{topic_id}/chat/sessions`** (201)

Request:
```json
{ "title": "Character Discussion" }
```
Response `201`:
```json
{
  "id": "uuid",
  "topic_id": "uuid",
  "title": "Character Discussion",
  "created_at": "...",
  "updated_at": "..."
}
```
✅ Field is `title` (not `name`).

**`GET /api/topics/{topic_id}/chat/sessions`**

Response `200`: `{ "sessions": [...] }`

**`GET /api/chat/sessions/{session_id}/messages`**

Response `200`:
```json
{
  "messages": [
    {
      "id": "uuid",
      "session_id": "uuid",
      "role": "user",
      "content": "刘备的性格特点是什么？",
      "evidence_json": null,
      "uncertainty": null,
      "created_at": "..."
    },
    {
      "id": "uuid",
      "session_id": "uuid",
      "role": "assistant",
      "content": "刘备是一个仁德的领袖...",
      "evidence_json": ["桃园结义展现了刘备的义气。"],
      "uncertainty": null,
      "created_at": "..."
    }
  ],
  "total": 2
}
```
Errors: `404` session not found.

**`POST /api/chat/sessions/{session_id}/messages`**

Request:
```json
{ "content": "刘备的性格特点是什么？" }
```
⚠️ Makes real LLM call with evidence retrieval. Content must be non-empty string (max 20000 chars).

Response `200`:
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "role": "assistant",
  "content": "刘备是一个仁德的领袖...",
  "evidence_json": ["桃园结义展现了刘备的义气。"],
  "uncertainty": null,
  "created_at": "..."
}
```
`evidence_json` will be `null` or empty if no evidence found. `uncertainty` is `null` when confident, a string when uncertain.

Errors: `404` session not found, `409` no provider configured, `422` content is null / empty / non-string / >20000 chars.

**`DELETE /api/chat/sessions/{session_id}`**

Response `200`: `{ "deleted": true }`
Errors: `404`.

---

## 4. Field Naming Confirmations

| Question | Answer |
|----------|--------|
| ChatSession: `title` or `name`? | ✅ `title` (consistent across model, router, API.md) |
| Provider response: `api_key` returned? | ✅ NEVER returned. Only `masked_api_key`. |
| AnalysisOutput.output_type values? | ✅ Lowercase: `overview`, `characters`, `relations`, `events`, `causality`, `themes` |
| Job status values? | ✅ Lowercase: `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| Job.job_type values? | ✅ Lowercase: `parse`, `analysis` |
| Document status? | `uploaded`, `parsed` |
| Topic enrich includes `document`? | ✅ Yes, with `id`, `original_filename`, `status`, `file_size_bytes`, `char_count` |
| Topic enrich includes `analysis_summary`? | ✅ Yes, keys are AnalysisType values, values are `"completed"` |

## 5. API.md vs Actual Code Discrepancies

| Area | API.md says | Actual code | Severity |
|------|-----------|-------------|----------|
| Provider prefix | `/api/model-providers` | `/api/providers` | ⚠️ Use `/api/providers` |
| Jobs API | Listed under "Analysis" section | Separate "Analysis Jobs (internal/dev)" section | Low |
| `PUT /api/topics/{id}/provider` | Documented but not implemented | Endpoint does NOT exist | ⚠️ Frontend: don't build this |
| Job defaults | `ANALYSIS_ALL` | `analysis` | ⚠️ Use `analysis` |
| `GET /api/storage` (global) | Documented | NOT implemented (topic-level `/api/topics/{id}/storage` exists) | Low |
| Analysis Output endpoint | `POST /api/topics/{id}/analysis` | `POST /api/topics/{id}/analysis/run` | ⚠️ Use `/run` |

## 6. Complete User Smoke Test Flow

The following is the full end-to-end flow from fresh install:

1. **Health**: `GET /api/health` → status ok
2. **Configure Provider**: `POST /api/providers` → create (fake or real)
3. **Test Provider** (optional, real): `POST /api/providers/{id}/test`
4. **Create Topic**: `POST /api/topics` → with or without provider_id
5. **Upload txt**: `POST /api/topics/{id}/documents/upload` → .txt file
6. **Check document**: `GET /api/topics/{id}/documents/current`
7. **Parse**: `POST /api/topics/{id}/parse`
8. **View chapters**: `GET /api/topics/{id}/chapters`
9. **View chunks**: `GET /api/topics/{id}/chunks?include_text=true&limit=10`
10. **Check storage**: `GET /api/topics/{id}/storage`
11. **Run analysis**: `POST /api/topics/{id}/analysis/run?limit_chunks=5` (needs real provider)
12. **View outputs**: `GET /api/topics/{id}/analysis/outputs`
13. **Create chat**: `POST /api/topics/{id}/chat/sessions`
14. **Send message**: `POST /api/chat/sessions/{sid}/messages` (needs real provider)
15. **View answer**: Check evidence_json and uncertainty in response
16. **Cleanup**: Delete chat session → delete analysis outputs → delete document → delete topic → delete provider

## 7. Backend Smoke Test Script

A standalone Python smoke test is available:

```bash
cd backend
# Safe mode (no real LLM):
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup

# Real LLM mode:
set DEEPSEEK_API_KEY=sk-...
python scripts/smoke_backend.py --real-llm --provider-api-key-env DEEPSEEK_API_KEY --cleanup
```
