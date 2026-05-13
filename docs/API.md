# LongNovelInsight v0.1.0 — API Reference

Base URL: `http://localhost:8000/api`

All request/response bodies are JSON. IDs are UUID strings.

> **Implementation stages:** Not all endpoints are implemented at once. Stage 1 (backend skeleton) covers only:
> - `GET /api/health`
> - `POST /api/topics`, `GET /api/topics`, `GET /api/topics/{topic_id}`, `DELETE /api/topics/{topic_id}`
>
> All other endpoints below are the full v0.1.0 target and will be implemented in subsequent stages.

## Health

### `GET /api/health`

Returns backend status and basic statistics.

**Response 200:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "topic_count": 3,
  "total_disk_usage_bytes": 5242880
}
```

---

## Topics

### `GET /api/topics`

List all topics.

**Response 200:**
```json
{
  "topics": [
    {
      "id": "uuid",
      "name": "Three Kingdoms",
      "description": "...",
      "provider_id": "uuid | null",
      "document": { "id": "uuid", "original_filename": "...", "status": "parsed" } | null,
      "analysis_summary": { "overview": "done", "characters": "running", ... },
      "disk_usage_bytes": 1048576,
      "created_at": "2026-05-10T12:00:00Z",
      "updated_at": "2026-05-10T12:00:00Z"
    }
  ]
}
```

### `POST /api/topics`

Create a new topic.

**Request:**
```json
{
  "name": "My Analysis",
  "description": "Optional description",
  "provider_id": "uuid (optional)"
}
```

**Response 201:** Full topic object.
**Errors:** `422` missing required fields. If `provider_id` is given and not found, returns `404`.

### `GET /api/topics/{topic_id}`

Get a single topic with full detail (document, chapters count, analysis statuses, chat sessions, storage).

**Response 200:** Full topic detail object.
**Errors:** `404` topic not found.

### `DELETE /api/topics/{topic_id}`

Delete a topic and all cascaded data (document, chapters, chunks, analyses, chat sessions/messages, jobs, files on disk).

**Response 200:**
```json
{ "deleted": true, "freed_bytes": 1048576 }
```
**Errors:** `404` topic not found.

### `PUT /api/topics/{topic_id}/provider`

Bind (or re-bind) a provider to a Topic.

**Request:**
```json
{ "provider_id": "uuid" }
```

**Response 200:** Full topic object.
**Errors:** `404` topic or provider not found.

---

## Documents

### `POST /api/topics/{topic_id}/documents/upload`

Upload a `.txt` file to a topic. Uses `multipart/form-data`.
Accepts UTF-8, UTF-8-SIG, GBK, GB18030, GB2312, UTF-16 encodings.
The file is normalized and saved as UTF-8 on the server.
`encoding` in the response indicates the actual source encoding used for decoding.

**Request:** File field `file` (`.txt` only, max 200 MB; limit configurable in `backend/config.py`).

**Response 201:**
```json
{
  "id": "uuid",
  "topic_id": "uuid",
  "original_filename": "novel.txt",
  "stored_filename": "original.txt",
  "file_type": "txt",
  "content_type": "text/plain",
  "encoding": "utf-8",
  "file_size_bytes": 1048576,
  "char_count": 500000,
  "storage_path": "topics/{topic_id}/source/original.txt",
  "status": "uploaded",
  "created_at": "...",
  "updated_at": "..."
}
```
**Errors:** `404` topic not found, `400` not a `.txt` file, `400` unsupported encoding (UTF-8 only), `409` topic already has a document, `413` file exceeds size limit.

### `GET /api/topics/{topic_id}/documents/current`

Get the current document metadata for a topic.

**Response 200:** Full document object.
**Errors:** `404` topic not found, `404` no document uploaded.

### `DELETE /api/topics/{topic_id}/documents/current`

Delete the current document and its file from disk.

**Response 200:** `{ "deleted": true, "freed_bytes": 1048576 }`
**Errors:** `404` topic not found, `404` no document uploaded.

---

## Parse

### `POST /api/topics/{topic_id}/parse`

Parse the uploaded novel: detect chapters, split into chunks, compute statistics. Idempotent — re-parsing replaces old chapters/chunks.

**Response 200:**
```json
{
  "chapter_count": 120,
  "chunk_count": 480,
  "char_count": 800000,
  "estimated_tokens": 533333
}
```
**Errors:** `404` topic not found, `404` no document uploaded, `409` original text file not found on disk.

### `GET /api/topics/{topic_id}/chapters`

List chapters ordered by chapter_index.

**Response 200:**
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

### `GET /api/topics/{topic_id}/chunks`

List chunks with pagination and optional text inclusion.

**Query params:**
- `include_text` (bool, default `false`) — include full chunk text in response
- `limit` (int, default `100`, max `1000`)
- `offset` (int, default `0`)

**Response 200:**
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
When `include_text=true`, the `text` field contains the full chunk content.

### `GET /api/topics/{topic_id}/storage`

Get storage usage for the topic.

**Response 200:**
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
      "chunks_size_bytes": 0,
      "analyses_size_bytes": 0,
      "total_bytes": 1048576
    }
  ]
}
```

---

## Model Providers

### `GET /api/model-providers`

List all configured LLM providers (API keys masked).

**Response 200:**
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
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

### `POST /api/model-providers`

Add a new LLM provider configuration.

**Request:**
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

**Response 201:** Full provider object (API key masked via `masked_api_key`; `api_key` is never returned).
**Errors:** `422` missing/invalid fields, `422` provider_type not `openai_compatible`, `409` name already exists.

### `GET /api/model-providers/{provider_id}`

Get a single provider by ID.

**Response 200:** Full provider object (API key masked).
**Errors:** `404` not found.

### `PATCH /api/model-providers/{provider_id}`

Update a provider configuration. All fields optional; only provided fields are updated.

**Request:** Any subset of provider fields.
**Response 200:** Updated provider object.
**Errors:** `404` not found, `409` name conflict, `422` invalid provider_type.

### `DELETE /api/model-providers/{provider_id}`

Delete a provider. Blocked if any Topic references it.

**Response 200:** `{ "deleted": true }`
**Errors:** `404` not found, `409` provider is in use by one or more Topics.

### `POST /api/model-providers/{provider_id}/test`

Test the connection by sending a minimal chat completion request.

**Response 200:**
```json
{
  "success": true,
  "provider_id": "uuid",
  "model_name": "deepseek-chat",
  "latency_ms": 450,
  "message": "Connection successful"
}
```
**Errors:** `404` provider not found. On connection failure, returns `200` with `"success": false` and an error message (API key sanitized).

---

## Analysis Outputs

### `POST /api/topics/{topic_id}/analysis/run`

Run structured analysis on the first N chunks using the bound LLM provider. Deletes previous outputs before running. v0.1.0 runs synchronously (all 6 types).

**Query params:** `limit_chunks` (int, default `5`) — max chunks to analyze.

**Response 200:**
```json
{
  "outputs": [
    {
      "id": "uuid",
      "topic_id": "uuid",
      "job_id": null,
      "output_type": "OVERVIEW",
      "title": "Work Overview",
      "content_json": { ... },
      "source_chunk_ids": ["uuid"],
      "evidence_quotes": ["..."],
      "confidence": 0.85,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "count": 6
}
```
**Errors:** `404` topic not found, `409` no document / not parsed / no provider.

### `GET /api/topics/{topic_id}/analysis/outputs`

List analysis outputs for a topic.

**Query params:** `output_type` (optional) — filter by type.

**Response 200:** `{ "outputs": [...], "count": N }`

### `DELETE /api/topics/{topic_id}/analysis/outputs`

Delete all analysis outputs for a topic.

**Response 200:** `{ "deleted": true, "count": N }`

---

## Chat

### `POST /api/topics/{topic_id}/chat/sessions`

Create a new chat session.

**Request:**
```json
{ "title": "Character Discussion" }
```

**Response 201:** Full session object `{ "id": "uuid", "topic_id": "uuid", "title": "...", "created_at": "...", "updated_at": "..." }`.
**Errors:** `404` topic not found.

### `GET /api/topics/{topic_id}/chat/sessions`

List chat sessions in a topic (most recent first).

**Response 200:** `{ "sessions": [...] }`

### `GET /api/chat/sessions/{session_id}/messages`

List messages in a session (chronological order).

**Response 200:**
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
      "role": "assistant",
      "content": "刘备是一个仁德的领袖...",
      "evidence_json": ["桃园结义..."],
      "uncertainty": null,
      "created_at": "..."
    }
  ],
  "total": 2
}
```
**Errors:** `404` session not found.

### `POST /api/chat/sessions/{session_id}/messages`

Send a message and get an evidence-grounded assistant response. The backend performs keyword retrieval from chunks and analysis outputs, then calls the LLM.

**Request:**
```json
{ "content": "刘备的性格特点是什么？" }
```

**Response 200:**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "role": "assistant",
  "content": "刘备是一个仁德的领袖...",
  "evidence_json": ["..."],
  "uncertainty": null,
  "created_at": "..."
}
```
**Errors:** `404` session not found, `409` no provider configured, `422` empty content.

### `DELETE /api/chat/sessions/{session_id}`

Delete a chat session and all its messages.

**Response 200:** `{ "deleted": true }`
**Errors:** `404` session not found.

---

## Storage

### `GET /api/storage`

Get storage usage overview.

**Response 200:**
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
      "chunks_size_bytes": 2097152,
      "analyses_size_bytes": 512000,
      "total_bytes": 3657728
    }
  ]
}
```

---

## Analysis Jobs

### `POST /api/topics/{topic_id}/analysis/jobs`

Create and run an analysis job. v0.1.0 runs a stub (no LLM calls).

**Query params:** `job_type` (default `ANALYSIS_ALL`). Valid types: `ANALYSIS_OVERVIEW`, `ANALYSIS_CHARACTERS`, `ANALYSIS_RELATIONS`, `ANALYSIS_EVENTS`, `ANALYSIS_CAUSALITY`, `ANALYSIS_THEMES`, `ANALYSIS_ALL`.

**Response 201:**
```json
{
  "job": { "id": "uuid", "topic_id": "uuid", "job_type": "ANALYSIS_ALL", "status": "SUCCEEDED", "progress_current": 6, "progress_total": 6, "message": "Analysis complete (stub)", ... },
  "items": [ { "id": "uuid", "job_id": "uuid", "item_type": "OVERVIEW", "status": "SUCCEEDED", ... }, ... ]
}
```
**Errors:** `404` topic not found, `409` no document / not parsed, `422` invalid job_type.

### `GET /api/topics/{topic_id}/analysis/jobs`

List all analysis jobs for a topic (most recent first).

**Response 200:** `{ "jobs": [...] }`

### `GET /api/topics/{topic_id}/analysis/status`

Get analysis status summary for a topic.

**Response 200:**
```json
{
  "topic_id": "uuid",
  "has_jobs": true,
  "latest_job": { ... },
  "analysis_types_completed": ["CHARACTERS", "OVERVIEW", ...]
}
```

### `GET /api/analysis/jobs/{job_id}`

Get a single job with its items.

**Response 200:** `{ "job": {...}, "items": [...] }`
**Errors:** `404` not found.

### `POST /api/analysis/jobs/{job_id}/cancel`

Cancel a pending or running job. Sets status to CANCELLED for the job and all items.

**Response 200:** `{ "job": {...}, "items": [...] }`
**Errors:** `404` not found.

---

## Common Error Responses

| Code | Meaning |
| ---- | ------- |
| 404 | Resource not found |
| 409 | Conflict (duplicate, state violation) |
| 413 | Upload too large |
| 415 | Unsupported file type |
| 422 | Validation error (missing/bad fields) |
| 500 | Internal server error |

All error responses follow:
```json
{ "detail": "Human-readable error message" }
```
