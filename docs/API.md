# LongNovelInsight v0.2.0-dev — API Reference

Base URL: `http://localhost:8000/api`

All request/response bodies are JSON. IDs are UUID strings.

> v0.1 endpoints marked as **(v1 legacy)**. v0.2 endpoints marked as **(v2 preferred)**.

## Health

### `GET /api/health`

Returns backend status and basic statistics.

**Response 200:**
```json
{
  "status": "ok",
  "version": "0.2.0-dev",
  "topic_count": 3,
  "total_disk_usage_bytes": 5242880
}
```

---

## Provider Presets

### `GET /api/provider-presets`

List all built-in provider presets (DeepSeek, OpenAI, Qwen, Moonshot, Custom).

**Response 200:**
```json
{
  "presets": [
    {
      "provider_key": "deepseek",
      "display_name": "DeepSeek",
      "base_urls": [{"label": "DeepSeek OpenAI-compatible", "base_url": "https://api.deepseek.com"}],
      "models": [
        {
          "model_name": "deepseek-v4-flash",
          "display_name": "DeepSeek V4 Flash",
          "context_window": 1000000,
          "recommended_max_output_tokens": 2048,
          "supports_thinking": true,
          "default_thinking_mode": "disabled"
        }
      ],
      "default_model_name": "deepseek-v4-flash"
    }
  ]
}
```

### `GET /api/provider-presets/{provider_key}`

Get a single preset.

### `GET /api/provider-presets/detect?base_url=...`

Detect a provider preset by base URL (normalizes trailing slash). Returns `provider_key="openai_compatible"` if unknown.

---

## Topic Provider Config

### `GET /api/topics/{id}/provider-config`

Get topic-level config overrides. Returns `{"config": null}` if not set.

### `PUT /api/topics/{id}/provider-config`

Upsert topic-level overrides. All fields are optional (null = inherit from provider/preset).

**Request:**
```json
{
  "model_name_override": "deepseek-v4-pro",
  "max_output_tokens_override": 4096,
  "temperature_override": 0.0,
  "thinking_mode_override": "enabled",
  "analysis_parallelism_override": 3
}
```

### `GET /api/topics/{id}/provider-config/effective`

Resolve effective config: Topic override > Provider default > Preset default. Returns `is_ready` boolean + `missing_fields` list.

### `GET /api/topics/{id}/analysis/recommendation`

Returns model recommendation based on document size (size_category, recommended model, tokens, temperature, parallelism, analysis mode).

### `POST /api/topics/{id}/provider-config/apply-recommendation`

Applies the recommendation to topic-level config.

---

## Topics

### `GET /api/topics`

List all topics with document and analysis summaries.

**Response 200:**
```json
{
  "topics": [
    {
      "id": "uuid",
      "name": "Three Kingdoms",
      "description": "...",
      "provider_id": "uuid | null",
      "storage_bytes": 1048576,
      "status": "created",
      "document": { "id": "uuid", "original_filename": "novel.txt", "status": "parsed", "file_size_bytes": 1048576, "char_count": 500000 } | null,
      "analysis_summary": { "overview": "completed", "characters": "completed" },
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

Get a single topic with full detail (document, analysis statuses, storage).

**Response 200:** Full topic detail object (same structure as list item).
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

Upload a `.txt` or `.epub` file to a topic. Uses `multipart/form-data`.

**TXT files:** Accepts UTF-8, UTF-8-SIG, GBK, GB18030, GB2312, UTF-16 encodings.
The file is normalized and saved as UTF-8 on the server.
`encoding` in the response indicates the actual source encoding used for decoding.

**EPUB files:** Validates the file is a valid zip container with `META-INF/container.xml`.
Does NOT parse chapters or extract text — the file is saved as-is for later parsing
(v0.3 Step 3+). `encoding` is set to `"epub"`, `char_count` is `0` (set after parse).

**Request:** File field `file` (`.txt` or `.epub`, max 200 MB; limit configurable in `backend/config.py`).

**TXT Response 201:**
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
  "metadata_json": null,
  "status": "uploaded",
  "created_at": "...",
  "updated_at": "..."
}
```

**EPUB Response 201:**
```json
{
  "id": "uuid",
  "topic_id": "uuid",
  "original_filename": "novel.epub",
  "stored_filename": "original.epub",
  "file_type": "epub",
  "content_type": "application/epub+zip",
  "encoding": "epub",
  "file_size_bytes": 524288,
  "char_count": 0,
  "storage_path": "topics/{topic_id}/source/original.epub",
  "metadata_json": "{\"source_format\":\"epub\",\"parsing_warnings\":[]}",
  "status": "uploaded",
  "created_at": "...",
  "updated_at": "..."
}
```

**Errors:**
- `404` topic not found
- `400` not a `.txt` or `.epub` file
- `400` unsupported TXT encoding
- `400` EPUB is not a valid zip file
- `400` EPUB missing `META-INF/container.xml`
- `409` topic already has a document
- `413` file exceeds size limit
- `422` TXT file empty or whitespace-only

### `GET /api/topics/{topic_id}/documents/current`

Get the current document metadata for a topic.

**Response 200:** Full document object.
**Errors:** `404` topic not found, `404` no document uploaded.

### `DELETE /api/topics/{topic_id}/documents/current`

Delete the current document and its file from disk.

**Response 200:** `{ "deleted": true, "freed_bytes": 1048576 }`
**Errors:** `404` topic not found, `404` no document uploaded.

### `GET /api/topics/{topic_id}/documents/current/metadata`

Get document metadata including parsed `metadata_json` (e.g., EPUB source format and parsing warnings).

**Response 200:**
```json
{
  "id": "uuid",
  "topic_id": "uuid",
  "original_filename": "novel.epub",
  "file_type": "epub",
  "encoding": "epub",
  "file_size_bytes": 524288,
  "char_count": 500000,
  "status": "parsed",
  "metadata": {
    "source_format": "epub",
    "parsing_warnings": []
  },
  "created_at": "2026-05-10T12:00:00Z",
  "updated_at": "2026-05-10T12:00:00Z"
}
```
For TXT files, `metadata` is `{}`. For EPUB files, it contains `source_format` and `parsing_warnings`.
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
      "chunks_size_bytes": 480000,
      "analyses_size_bytes": 0,
      "total_bytes": 1528576
    }
  ]
}
```

---

## Providers

### `GET /api/providers`

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

### `POST /api/providers`

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

### `GET /api/providers/{provider_id}`

Get a single provider by ID.

**Response 200:** Full provider object (API key masked).
**Errors:** `404` not found.

### `PATCH /api/providers/{provider_id}`

Update a provider configuration. All fields optional; only provided fields are updated.

**Request:** Any subset of provider fields.
**Response 200:** Updated provider object.
**Errors:** `404` not found, `409` name conflict, `422` invalid provider_type.

### `DELETE /api/providers/{provider_id}`

Delete a provider. Blocked if any Topic references it.

**Response 200:** `{ "deleted": true }`
**Errors:** `404` not found, `409` provider is in use by one or more Topics.

### `POST /api/providers/{provider_id}/test`

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
      "output_type": "overview",
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

## Search

### `POST /api/topics/{topic_id}/search`

Search chunks via FTS5 full-text index with keyword fallback for CJK queries.

**Request:**
```json
{
  "query": "刘备 桃园",
  "limit": 20,
  "include_snippets": true,
  "methods": ["fts", "keyword_fallback"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | str | (required) | Search query (1-500 chars) |
| `limit` | int | `20` | Max results (1-100) |
| `include_snippets` | bool | `true` | Include snippet text in results |
| `methods` | list[str] | `["fts", "keyword_fallback"]` | Search methods to use |

**Response 200:**
```json
{
  "query": "刘备 桃园",
  "results": [
    {
      "chunk_id": "uuid",
      "topic_id": "uuid",
      "chapter_index": 0,
      "chunk_index": 5,
      "title": "第一章 宴桃园豪杰三结义",
      "snippet": "刘备和关羽张飞在桃园...",
      "score": 2.35,
      "method": "fts"
    }
  ],
  "trace_id": null
}
```
`trace_id` is reserved for future retrieval trace support (always `null` in v0.3).

**Errors:** `404` topic not found, `422` query empty/too long/limit out of range/invalid methods/boolean limit.

---

### `POST /api/topics/{topic_id}/retrieve`

Hybrid retrieval across chunks (FTS + keyword fallback), analysis outputs, and extracted atoms. Returns ranked, deduplicated, score-normalized candidates with source locators. Optionally persists a retrieval trace for debugging.

**Request:**
```json
{
  "query": "曹操 赤壁",
  "top_k": 8,
  "methods": ["fts", "keyword_fallback", "structured", "analysis_output"],
  "persist_trace": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | str | (required) | Search query (1-500 chars) |
| `top_k` | int | `8` | Max results (1-50) |
| `methods` | list[str] | `["fts", "keyword_fallback", "structured", "analysis_output"]` | Candidate generators + optional `semantic_rerank` |
| `persist_trace` | bool | `false` | Save a RetrievalTrace and return its ID |

Valid methods:
- `fts` — SQLite FTS5 full-text search over chunk text/title
- `keyword_fallback` — LIKE-based substring search (CJK fallback)
- `structured` — ExtractedAtom search by canonical name, aliases, evidence quotes
- `analysis_output` — AnalysisOutput search by title, content, evidence quotes
- `semantic_rerank` — (optional, disabled by default) re-rank lexical/structured results with embedding similarity. Must be combined with at least one retrieval method. When disabled (`ENABLE_SEMANTIC_RERANK=false`), a `warning` is returned and results are unchanged.

**Response 200:**
```json
{
  "query": "曹操 赤壁",
  "results": [...],
  "trace_id": "uuid-or-null",
  "warning": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | str | `chunk`, `analysis_output`, or `atom` |
| `source_id` | str | ID of the matching source (chunk/output/atom) |
| `chunk_id` | str or null | Source chunk ID when available |
| `chapter_index` | int or null | Chapter index when available |
| `chunk_index` | int or null | Chunk index when available |
| `title` | str | Display title |
| `snippet` | str | Text excerpt centered on match |
| `score` | float | Relevance score normalized to [0, 1] |
| `method` | str | Method that produced the hit; may be combined (`fts+keyword_fallback`) |
| `matched_terms` | list[str] | Query tokens found in the matched text |
| `source_locator` | dict or null | Parsed `source_locator_json` when a source chunk is linked |
| `trace_id` | str or null | RetrievalTrace ID when `persist_trace: true`; `null` otherwise |
| `warning` | str or null | Warning message (e.g. `semantic_rerank` requested but disabled); `null` normally |

**Errors:** `404` topic not found, `422` query empty/too long/top_k out of range/invalid methods/boolean top_k/semantic_rerank alone.

---

### `GET /api/topics/{topic_id}/chunks/{chunk_id}/locator`

Return source locator info and a short context excerpt for a chunk.

**Response 200:**
```json
{
  "chunk_id": "uuid",
  "topic_id": "uuid",
  "chapter_index": 0,
  "chunk_index": 3,
  "locator": {
    "source_href": "chapter1.xhtml",
    "offset": 450
  },
  "excerpt": "刘备和关羽张飞在桃园..."
}
```
`locator` contains the parsed `source_locator_json` (empty object for TXT files).
`excerpt` is the first 200 characters of the chunk text.

**Errors:** `404` chunk not found (including wrong topic).

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

List messages in a session (chronological order). `evidence_json` may be either old-format string arrays or new-format structured objects (see POST /messages).

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
      "evidence_json": [
        {
          "text": "刘备与关羽张飞在桃园结为兄弟...",
          "source_type": "chunk",
          "source_id": "uuid",
          "chunk_id": "uuid",
          "title": "",
          "method": "legacy",
          "score": 2.0,
          "locator": null
        }
      ],
      "uncertainty": null,
      "created_at": "..."
    }
  ],
  "total": 2
}
```
**Errors:** `404` session not found.

### `POST /api/chat/sessions/{session_id}/messages`

Send a message and get an evidence-grounded assistant response. The backend performs hybrid retrieval (FTS + keyword fallback + structured atom search + analysis output search) with legacy fuzzy fallback for long CJK queries, then calls the LLM. A `RetrievalTrace` is persisted for every request.

**Request:**
```json
{ "content": "刘备的性格特点是什么？" }
```

**Response 200 (new — structured evidence):**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "role": "assistant",
  "content": "刘备是一个仁德的领袖...",
  "evidence_json": [
    {
      "text": "刘备与关羽张飞在桃园结为兄弟...",
      "source_type": "chunk",
      "source_id": "uuid",
      "chunk_id": "uuid",
      "title": "",
      "method": "legacy",
      "score": 2.0,
      "locator": null
    }
  ],
  "uncertainty": null,
  "created_at": "..."
}
```
`evidence_json` items: `text` (snippet), `source_type` (chunk|analysis_output|atom), `source_id`, `chunk_id` (nullable), `title`, `method` (fts|keyword_fallback|structured|analysis_output|legacy), `score` (float), `locator` (dict|null).

Backward compatibility: messages created before v0.3 may have `evidence_json` as a string array `["evidence string", ...]`. Both formats are valid.

When retrieval finds no evidence, the service forces an `uncertainty` note to guard against LLM hallucination. An empty RetrievalTrace (`results_json: "[]"`) is still persisted for debugging.

**Errors:** `404` session not found, `409` no provider configured, `422` content must be a non-empty string (max 20000 chars).

### `DELETE /api/chat/sessions/{session_id}`

Delete a chat session and all its messages.

**Response 200:** `{ "deleted": true }`
**Errors:** `404` session not found.

### `DELETE /api/chat/sessions/messages/{message_id}`

Delete a message. If it's a user message, the following assistant reply is also deleted.

**Response 200:** `{ "deleted": true }`
**Errors:** `404` message not found.

---

## Entities & Similar Scenes (v0.3)

### `GET /api/topics/{topic_id}/entities/{entity_id}/evidence`

Find all evidence for an entity by its atom `id`, `stable_id`, or `canonical_name`. Returns matching atoms, their source chunks (with locators, <=300 char excerpts), and related AnalysisOutputs that share source chunks. All results capped by `limit`.

**Query params:** `limit` (int, default 20, 1-50).

**Response 200:**
```json
{
  "entity_id": "char_liubei",
  "canonical_name": "刘备",
  "atoms": [
    {
      "id": "uuid",
      "atom_type": "character",
      "stable_id": "char_liubei",
      "canonical_name": "刘备",
      "title": "刘玄德",
      "summary": null,
      "confidence": 0.95,
      "evidence_quotes": ["刘备出场。"],
      "chapter_index": 0,
      "chunk_index": 0
    }
  ],
  "chunks": [
    {
      "id": "uuid",
      "chapter_index": 0,
      "chunk_index": 0,
      "excerpt": "刘备和关羽在桃园结义...",
      "locator": {"source_type": "txt", "href": "txt://original", "chunk_index": 0}
    }
  ],
  "outputs": [
    {
      "id": "uuid",
      "output_type": "characters",
      "title": "刘备分析",
      "excerpt": "刘备是主角..."
    }
  ]
}
```
Chunks from other topics are excluded. Entity not found returns 200 with empty arrays.

**Errors:** `404` topic not found.

---

### `GET /api/topics/{topic_id}/similar-scenes`

Find scenes similar to a seed chunk or a free-text query using lexical + structured retrieval (no embeddings).

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `chunk_id` | str | null | Seed chunk ID (builds query from chunk text + associated atom names) |
| `query` | str | null | Free-text search query (1-500 chars) |
| `limit` | int | 10 | Max results (1-30) |

At least one of `chunk_id` or `query` is required. When both given, `chunk_id` takes priority. The seed chunk is excluded from results in `chunk_id` mode.

**Response 200:**
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "chapter_index": 1,
      "chunk_index": 3,
      "title": "第二章",
      "snippet": "曹操率军南下，欲取江南...",
      "score": 0.85,
      "locator": {"source_type": "txt", "href": "txt://original", "chunk_index": 3}
    }
  ]
}
```

**Errors:** `404` topic/chunk not found, `422` missing both params/empty query.

---

## Analysis Jobs (internal / dev)

> The analysis jobs API tracks task execution. In v0.1.0, jobs run synchronously with real LLM calls (for `analysis` type) or as stubs (for `parse` type). This is an internal API; the frontend should prefer `POST /api/topics/{id}/analysis/run` for analysis.

### `POST /api/topics/{topic_id}/analysis/jobs`

Create and run an analysis stub job.

**Query params:** `job_type` (default `analysis`). Valid types: `parse`, `analysis`.

**Response 201:**
```json
{
  "job": { "id": "uuid", "topic_id": "uuid", "job_type": "analysis", "status": "succeeded", "progress_current": 6, "progress_total": 6, "message": "Analysis complete (stub)", ... },
  "items": [ { "id": "uuid", "job_id": "uuid", "item_type": "overview", "status": "succeeded", ... }, ... ]
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
  "analysis_types_completed": ["overview", "characters", ...]
}
```

### `GET /api/analysis/jobs/{job_id}`

Get a single job with its items.

**Response 200:** `{ "job": {...}, "items": [...] }`
**Errors:** `404` not found.

### `POST /api/analysis/jobs/{job_id}/cancel`

Cancel a pending or running job.

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

---

## v0.2 Analysis Runs (v2 preferred)

### `GET /api/topics/{id}/chunks/meta`

Lightweight chunk statistics without text content.

**Response 200:**
```json
{
  "topic_id": "uuid", "document_id": "uuid",
  "chunk_count": 120, "chapter_count": 30,
  "total_chars": 500000, "estimated_tokens": 333333,
  "first_chunk_index": 0, "last_chunk_index": 119,
  "chunks_by_chapter": [
    {"chapter_index": 0, "title": "第一章", "chunk_count": 4, "char_count": 12000, "estimated_tokens": 8000}
  ]
}
```

---

### `POST /api/topics/{id}/analysis/runs` (201)

Create and start a v2 staged analysis run. Runs in background thread.

**Request:**
```json
{
  "mode": "preview",
  "requested_types": ["overview", "characters", "relations", "events", "causality", "themes"],
  "limit_chunks": 5,
  "chunk_index_start": null, "chunk_index_end": null,
  "chapter_index_start": null, "chapter_index_end": null,
  "force": false, "start_immediately": true
}
```

**Response 201:**
```json
{
  "run": {"id": "uuid", "topic_id": "uuid", "mode": "preview", "status": "pending", "progress_total": 8},
  "status_url": "/api/analysis/runs/{id}"
}
```
Errors: `404` topic, `409` no chunks/no provider/already running, `422` invalid mode/range/requested_types.

---

### `GET /api/topics/{id}/analysis/runs`

List all v2 runs for a topic, most recent first.

---

### `GET /api/analysis/runs/{id}`

Run status with extraction, merge, and final stage summaries.

**Response 200:**
```json
{
  "run": {"id": "uuid", "status": "succeeded", "extraction_succeeded": 3, "extraction_failed": 0,
          "merge_succeeded": 5, "merge_failed": 0, "final_succeeded": 5, "final_failed": 0,
          "progress_current": 13, "progress_total": 14, "total_tokens": 15000, ...},
  "extractions": [{"id": "uuid", "chunk_id": "uuid", "status": "succeeded", "attempt_count": 1}],
  "merge": {"total": 5, "succeeded": 5, "outputs": [...]},
  "final": {"total": 5, "succeeded": 5, "outputs": [{"id": "uuid", "output_type": "characters", "title": "Character List"}]}
}
```

---

### `POST /api/analysis/runs/{id}/cancel`

Cancel a pending or running run.

---

### `POST /api/analysis/runs/{id}/retry-failed`

Retry all failed chunks, then re-run merge and final stages. Background execution.

---

### `POST /api/analysis/runs/{id}/resume?retry_failed=true`

Resume an interrupted run. If `retry_failed=true` (default), also retry failed chunks.

---

## v0.2 Legacy Bridge

### `POST /api/topics/{id}/analysis/run?pipeline=v2`

Legacy endpoint with `pipeline=v2` creates a v2 AnalysisRun. Default `pipeline=v1` preserves original v0.1 behavior.

### `GET /api/topics/{id}/analysis/outputs?run_id=X&latest_only=true`

New query params: `run_id` filters by v2 run, `latest_only` returns one per output_type. Default listing excludes `merge_*` intermediates.

### `GET /api/topics/{id}/analysis/status`

Now includes `latest_v2_run` summary and `v2_available: true`.
