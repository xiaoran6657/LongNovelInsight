# LongNovelInsight Backend

Python + FastAPI + SQLModel + SQLite backend for local-first LLM-powered long-novel analysis.

## Quick Start

```bash
conda activate LongNovelInsight
cd backend
pip install -e ".[dev]"
uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/health
pytest -v
ruff check . && ruff format --check .
```

## Architecture

```
backend/
├── main.py                  # FastAPI app, CORS, lifespan (init_db)
├── config.py                # DATA_DIR, DB_PATH, UPLOAD_MAX_BYTES (200MB)
├── db.py                    # SQLite engine + get_session() dependency
├── pyproject.toml           # Dependencies: fastapi, uvicorn, sqlmodel, httpx, python-multipart
├── provider_presets.py      # Provider preset catalog (DeepSeek, OpenAI, Qwen, Moonshot)
├── models/
│   ├── enums.py             # StrEnum: AnalysisType, JobType, JobStatus, AnalysisMode, AtomType
│   ├── __init__.py          # Exports all table models → SQLModel.metadata
│   ├── topic.py             # Topic (provider_id FK→model_provider)
│   ├── model_provider.py    # ModelProvider (masked_api_key @property, validators)
│   ├── topic_provider_config.py # TopicProviderConfig (topic-level config overrides)
│   ├── document.py          # Document (topic_id unique, status, encoding)
│   ├── chapter.py           # Chapter (chapter_index, title, char offsets)
│   ├── chunk.py             # Chunk (text in SQLite, estimated_tokens)
│   ├── analysis_output.py   # AnalysisOutput (content_json, evidence, confidence, run_id FK)
│   ├── analysis_run.py      # AnalysisRun (v2 staged pipeline lifecycle)
│   ├── local_extraction.py  # LocalExtraction (per-chunk LLM extraction result)
│   ├── extracted_atom.py    # ExtractedAtom (normalized atomic facts, stable_id)
│   ├── analysis_artifact.py # AnalysisArtifact (large JSON file storage metadata)
│   ├── chat.py              # ChatSession, ChatMessage (+ ChatMessageCreate validation)
│   ├── job.py               # Job (job_type: parse|analysis, progress, metadata)
│   └── job_item.py          # JobItem (item_type: AnalysisType values)
├── routers/
│   ├── health.py            # GET /api/health
│   ├── topics.py            # CRUD + enriched list/detail (document, analysis_summary)
│   ├── model_providers.py   # CRUD + POST test (prefix: /api/providers)
│   ├── provider_presets.py  # GET presets catalog + detect by base_url
│   ├── topic_provider_config.py # Per-topic config, effective config, recommendation
│   ├── documents.py         # upload, get current, delete (with cascade)
│   ├── parse.py             # parse, chapters, chunks, storage
│   ├── analysis_jobs.py     # job CRUD, status (with latest_v2_run), cancel
│   ├── analysis_outputs.py  # run analysis (v1 + pipeline=v2 bridge), list/delete outputs
│   ├── analysis_runs.py     # v2 run CRUD, retry-failed, resume, cancel
│   └── chat.py              # session CRUD, send message with validation (two routers)
├── services/
│   ├── llm_client.py        # OpenAICompatibleLLMClient (httpx, 2 retries, 120s timeout)
│   ├── prompt_loader.py     # Load v1 + v2 prompt templates from prompts/ dir
│   ├── analysis_service.py  # v1: run_single_analysis_output + batch-map-merge pipeline
│   ├── analysis_worker.py   # v1 worker: run_one_analysis_type (no DB, pure LLM + retry)
│   ├── job_service.py       # run_analysis_job (async parallel execution, bounded pool)
│   ├── provider_config_service.py # Effective config resolution + recommendations
│   ├── document_service.py  # upload (multi-encoding→UTF-8), delete with v2 cascade
│   ├── chat_service.py      # send_user_message (evidence retrieval + history + LLM)
│   ├── retrieval_service.py # Keyword retrieval (stopwords, _make_excerpt, top_k=8)
│   ├── topic_service.py     # delete_topic (full cascade including v2 data), summary helpers
│   ├── storage.py           # File I/O with path traversal protection (_is_safe)
│   ├── parser_service.py    # Chapter detection (regex), chunk splitting
│   ├── provider_test_service.py # Connection test (minimal LLM call)
│   │   # ── v0.2 services ──
│   ├── stable_id_service.py       # Canonical stable ID generation (CJK-safe)
│   ├── atom_normalizer.py         # JSON → ExtractedAtom normalization (contract-strict)
│   ├── analysis_selection_service.py # Chunk meta + selection (preview/range/full/incremental)
│   ├── analysis_response_parser.py   # LLM JSON response parsing + validation
│   ├── local_extraction_worker.py    # Single-chunk v2 local_extraction (pure function, retry)
│   ├── analysis_run_service.py       # v2 orchestrator: create/start/cancel/retry/resume
│   ├── merge_service.py              # Deterministic merge (8 types, Python-only)
│   ├── final_output_service.py       # Merge → v0.1-compatible final AnalysisOutput
│   └── artifact_storage_service.py   # Hybrid storage (inline + disk artifacts, 64KB threshold)
├── prompts/
│   ├── overview.md, characters.md, relations.md, events.md, causality.md, themes.md
│   └── v2/                   # v0.2 staged pipeline prompts
│       ├── local/            # local_extraction prompt
│       └── merge/            # merge_<type> prompts
├── tests/                   # 367 passing tests (see test section below)
└── scripts/
    ├── smoke_backend.py     # v0.1 smoke test (safe + --real-llm modes)
    └── smoke_v2_backend.py  # v0.2 smoke test (safe + --real-llm modes)
```

## Data Model (15 tables: 11 v0.1 + 4 v0.2)

```
ModelProvider  ?──*  Topic
Topic          1──1  TopicProviderConfig
Topic          1──1  Document
Document       1──*  Chapter
Chapter        1──*  Chunk
Topic          1──*  AnalysisOutput
Topic          1──*  ChatSession
ChatSession    1──*  ChatMessage
Topic          1──*  Job
Job            1──*  JobItem
Topic          1──*  AnalysisRun (v2)
AnalysisRun    1──*  LocalExtraction (v2)
Topic          1──*  LocalExtraction (v2)
LocalExtraction1──*  ExtractedAtom (v2)
Topic          1──*  ExtractedAtom (v2)
Topic          1──*  AnalysisArtifact (v2)
```

## Enums (all lowercase StrEnum)

| Enum | Values |
|------|--------|
| `AnalysisType` | `overview`, `characters`, `relations`, `events`, `causality`, `themes` |
| `AnalysisMode` (v2) | `preview`, `range`, `full`, `incremental` |
| `AtomType` (v2) | `character`, `event`, `relation`, `causal_link`, `theme_signal`, `worldbuilding`, `foreshadowing`, `open_question` |
| `JobType` | `parse`, `analysis` |
| `JobStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled`, `partial_success` |
| `JobItemStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| `DocumentStatus` | `uploaded`, `parsing`, `parsed`, `failed` |
| `TopicStatus` | `created`, `uploaded`, `parsed`, `analyzing`, `ready`, `failed` |

## API Endpoints (38+ endpoints)

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Status, version, topic count, disk usage |

### Providers (`/api/providers`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/providers` | List all (api_key masked) |
| POST | `/api/providers` | Create (validates: name, provider_type, base_url, api_key, model_name) |
| GET | `/api/providers/{id}` | Get one |
| PATCH | `/api/providers/{id}` | Update |
| DELETE | `/api/providers/{id}` | Delete (blocked if in use by Topic) |
| POST | `/api/providers/{id}/test` | Connection test |

### Provider Presets (`/api/provider-presets`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/provider-presets` | List all provider presets (DeepSeek, OpenAI, Qwen, Moonshot, Custom) |
| GET | `/api/provider-presets/{key}` | Get one preset by provider_key |
| GET | `/api/provider-presets/detect?base_url=...` | Detect provider preset by base_url (normalizes trailing slash) |

### Topic Provider Config (`/api/topics/{id}`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics/{id}/provider-config` | Get topic-level config overrides |
| PUT | `/api/topics/{id}/provider-config` | Upsert topic config overrides (model, tokens, temp, thinking, parallelism) |
| GET | `/api/topics/{id}/provider-config/effective` | Resolve effective config (topic > provider > preset) |
| GET | `/api/topics/{id}/analysis/recommendation` | Get model recommendation based on document size |
| POST | `/api/topics/{id}/provider-config/apply-recommendation` | Apply recommendation to topic config |

### Topics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics` | List (with document + analysis_summary) |
| POST | `/api/topics` | Create (provider_id validated) |
| GET | `/api/topics/{id}` | Detail (document, analysis_summary) |
| DELETE | `/api/topics/{id}` | Delete (full cascade) |

### Documents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/documents/upload` | Upload .txt (multi-encoding→UTF-8) |
| GET | `/api/topics/{id}/documents/current` | Get current |
| DELETE | `/api/topics/{id}/documents/current` | Delete (cascades derived data) |

### Parse
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/parse` | Parse novel (idempotent; ?force=true to re-parse) |
| GET | `/api/topics/{id}/chapters` | List chapters |
| GET | `/api/topics/{id}/chunks` | List chunks (?include_text, limit, offset) |
| GET | `/api/topics/{id}/storage` | Storage usage (real chunk/analysis sizes) |

### Analysis Outputs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/run` | Run structured analysis (?pipeline=v1|v2, ?limit_chunks) |
| GET | `/api/topics/{id}/analysis/outputs` | List (?output_type, ?run_id, ?latest_only) |
| DELETE | `/api/topics/{id}/analysis/outputs` | Delete all (?run_id for targeted) |

### v0.2 Analysis Runs (`/api/analysis/runs` and `/api/topics/{id}/analysis/runs`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/runs` | Create and start v2 staged run (201) |
| GET | `/api/topics/{id}/analysis/runs` | List runs for topic |
| GET | `/api/topics/{id}/chunks/meta` | Lightweight chunk statistics |
| GET | `/api/analysis/runs/{id}` | Run status with extraction/merge/final summaries |
| POST | `/api/analysis/runs/{id}/cancel` | Cancel pending/running run |
| POST | `/api/analysis/runs/{id}/retry-failed` | Retry failed chunks, re-merge, re-final |
| POST | `/api/analysis/runs/{id}/resume` | Resume interrupted run (?retry_failed=true) |

### Analysis Jobs (internal/dev)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/jobs` | Create job (?job_type=analysis) |
| GET | `/api/topics/{id}/analysis/jobs` | List jobs |
| GET | `/api/topics/{id}/analysis/status` | Status summary |
| GET | `/api/analysis/jobs/{id}` | Job detail with items |
| POST | `/api/analysis/jobs/{id}/cancel` | Cancel job |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/chat/sessions` | Create session |
| GET | `/api/topics/{id}/chat/sessions` | List sessions |
| GET | `/api/chat/sessions/{id}/messages` | List messages |
| POST | `/api/chat/sessions/{id}/messages` | Send message (content validation, 422 on null/empty/non-string) |
| DELETE | `/api/chat/sessions/{id}` | Delete session + messages |
| DELETE | `/api/chat/sessions/messages/{id}` | Delete message + following assistant reply |

## Analysis Workflow

### Provider Config Resolution

```
TopicProviderConfig override  >  ModelProvider default  >  ProviderPreset default
```

1. **Providers page** stores credentials and global defaults (base_url, model_name, temperature, etc.).
2. **Topic page** stores per-novel overrides in `TopicProviderConfig` — model_name, max_output_tokens, temperature, thinking_mode, parallelism.
3. **Effective config** merges at analysis/chat runtime. Editing a Topic's config does NOT mutate the global Provider.

### Analysis Modes

| Mode | Condition | Behavior |
|------|-----------|----------|
| `preview` | Small/medium text, limit_chunks set | Runs analysis on a subset of chunks. Fast, low cost. |
| `direct` | Up to ~300k chars | Runs all 6 analysis types on selected chunks via async parallel jobs. |
| `map_reduce_required` | >1M chars | Disabled in v0.1 — use preview mode or wait for v0.2 map-reduce pipeline. |

**Recommendation engine** (`GET /api/topics/{id}/analysis/recommendation`) inspects document size, chunk count, estimated tokens, and selected provider to recommend: model, max_output_tokens, temperature, thinking_mode, parallelism, limit_chunks, and analysis mode.

### Async Job Flow

```
POST /api/topics/{id}/analysis/jobs  →  202 (job pending)
Frontend polls GET /api/topics/{id}/analysis/status  →  progress, timings, token usage
Job: pending → running → succeeded / partial_success / failed / cancelled
```

- Worker threads call LLM only; main thread writes DB results.
- Bounded parallelism via `ThreadPoolExecutor(max_workers=1-6, default=3)`.
- Per-type retry: max 2 attempts, exponential backoff, JSON-length doubling.
- Partial success: failed types stored in metadata; successful outputs saved.
- Cancel marks job cancelled; in-flight LLM calls may still complete but results are discarded.

### Job Metadata (token usage + timings)

```json
{
  "parallelism": 3,
  "model_name": "deepseek-v4-flash",
  "thinking_mode": "disabled",
  "type_timings": { "overview": 35.2, "characters": 68.1 },
  "usage_by_type": {
    "overview": { "prompt_tokens": 12000, "completion_tokens": 1000, "total_tokens": 13000 }
  },
  "failed_types": [{ "output_type": "causality", "error": "JSON parse failed" }]
}
```

### Performance Recommendations

- **Use fast non-thinking model** for structured extraction (e.g., `deepseek-v4-flash` with thinking disabled). Thinking mode adds latency and cost without benefiting structured JSON extraction.
- **Set bounded parallelism** (default 3). Higher values (>4) may trigger provider rate limits.
- **Enable thinking only when quality requires it** — primarily for complex reasoning tasks, not structured extraction.
- **Large novels (>300k chars)** should use preview mode with limited chunks. Full direct analysis on large texts repeats selected chunks ~6 times, consuming significant API credits.
- **v0.1 limitation**: Direct structured analysis sends selected chunks once per output_type (6 separate LLM calls with identical prefix).
- **v0.2 staged pipeline**: Each chunk is sent to the LLM once (local_extraction), then deterministic merge and final stages run without LLM (~4× token savings). Full retry/resume/idempotency support.

## Test Summary (367 tests, all passing)

| File | Tests | Key areas |
|------|-------|-----------|
| `test_documents.py` | 24 | 8 encodings, delete cascade, empty/whitespace reject, path safety |
| `test_analysis_jobs.py` | 20 | Job CRUD, item failure, cancel, no duplicates |
| `test_model_providers.py` | 16 | CRUD, default uniqueness, api_key masking |
| `test_analysis_outputs.py` | 17 | 6-type outputs, evidence, batch-merge, late characters |
| `test_parser_service.py` | 17 | Chapter detection (CN/EN), chunking, token estimation |
| `test_chat.py` | 17 | Session CRUD, send/validate, evidence, history, delete message |
| `test_parse_api.py` | 13 | Parse API, chunks pagination, storage, idempotent |
| `test_topics.py` | 17 | CRUD, provider FK, topic config, effective config, cascade delete |
| `test_retrieval_service.py` | 8 | Keyword match, stopwords filter, excerpt position, empty query |
| `test_llm_client.py` | 8 | Normal/401/network/invalid JSON/empty choices/retry/api_key leak |
| `test_model_provider_test.py` | 4 | Provider test success/404/LLM error/api_key leak |
| `test_health.py` | 1 | Health endpoint |
| `test_stable_id.py` (v2) | 26 | Stable ID generation, CJK safety, idempotency |
| `test_analysis_run.py` (v2) | 15 | AnalysisRun CRUD, migration, status transitions |
| `test_analysis_runs.py` (v2) | 28 | v2 pipeline, retry, resume, idempotency, error classification |
| `test_analysis_selection.py` (v2) | 22 | Chunk meta, preview/range/full/incremental selection |
| `test_atom_normalizer.py` (v2) | 15 | JSON normalization, evidence/confidence contract |
| `test_v2_prompts.py` (v2) | 28 | v1+v2 prompt loading, JSON parsing, validation |
| `test_local_extraction_worker.py` (v2) | 13 | Single-chunk extraction, retry, api_key mask |
| `test_merge_service.py` (v2) | 17 | Deterministic merge (8 types), dedup, per-item fields |
| `test_final_output_service.py` (v2) | 11 | Merge → v0.1-compatible final outputs |
| `test_artifact_storage.py` (v2) | 6 | Hybrid storage, write/read/delete, threshold |

All tests mock LLM calls. No real external API calls in CI.

## Key Design Decisions

- **Provider presets**: Built-in catalog of known providers (DeepSeek, OpenAI, Qwen/Alibaba, Kimi/Moonshot) with base URLs and model metadata. Custom OpenAI-compatible providers also supported. See `provider_presets.py`.
- **Provider vs. Topic config**: Provider stores credentials and global defaults. `TopicProviderConfig` stores per-Topic overrides (model, tokens, temperature, thinking mode, parallelism). Effective config resolves Topic override > Provider default > Preset default. Editing a Topic's config never mutates the global Provider.
- **Async parallel jobs**: Analysis runs the 6 output types in parallel via `ThreadPoolExecutor` (bounded 1-6). Worker threads only call LLM; the main thread writes DB results. Status pollable via `GET /api/topics/{id}/analysis/status`.
- **Prompt-cache-friendly construction**: Shared system instructions and novel chunks form a stable prefix across all 6 output-type LLM calls. Task-specific schema and instructions are appended last, maximizing cache hit rates on providers that support prompt caching.
- **Per-type token budgets**: Each of the 6 analysis types has a tuned `max_tokens` limit (overview: 1024, characters: 3072, relations: 2048, events: 3072, causality: 2048, themes: 1536). Overridable by effective config.
- **Retry policy**: Per-type retries (max 2) with exponential backoff for 429/5xx/timeout/rate-limit errors. JSON parse failures retry once with doubled max_tokens.
- **Thinking mode**: DeepSeek-compatible `extra_body={"thinking": {"type": "enabled/disabled"}}`. Only sent when provider preset supports thinking. Non-thinking (disabled) recommended for structured extraction — faster, cheaper, and temperature has effect.
- **No file-per-chunk**: v0.1 stores chunk text in SQLite columns. v0.2 adds hybrid storage: large analysis JSON (>64KB) stored on disk under `data/topics/{id}/artifacts/` with `analysis_artifact` table tracking; small JSON stays inline in SQLite.
- **Batch-map-merge**: For novels with many chunks, analysis uses a two-stage pipeline: partial analysis per batch, then multi-level merge.
- **api_key safety**: `ModelProvider.masked_api_key` @property; all API responses exclude raw `api_key`; errors use `mask_api_key()` before logging.
- **Path traversal protection**: `storage._is_safe()` uses `Path.relative_to()` instead of string `startswith`.
- **Keyword retrieval**: Substring + Chinese character overlap (filtered by ~70 stopwords) + English word overlap. No vector DB.
- **Chat grounding**: Answers must include evidence/uncertainty JSON fields; recent 6 messages included for pronoun resolution.
- **Chat token tracking**: ChatMessage stores `prompt_tokens`, `completion_tokens`, `total_tokens`, and `model_used` from LLM API responses for per-model usage statistics in the UI.
- **Chunk text normalization**: Parser collapses excessive blank lines and strips trailing whitespace before storing chunk text, reducing token waste in LLM prompts.
- **Schema migration**: `init_db()` runs incremental `ALTER TABLE ADD COLUMN` migrations for new fields on existing databases.

## Dependencies

```toml
[dependencies]
fastapi>=0.115.0
uvicorn>=0.30.0
sqlmodel>=0.0.22
httpx>=0.27.0
python-multipart>=0.0.12

[dev]
pytest>=8.0
ruff>=0.8.0
```

## Forbidden (v0.1.0)

- Login/auth/multi-user
- Cloud sync/remote storage
- .epub or PDF parsing
- Docker/containerization
- LangChain/LlamaIndex
- Vector databases (Chroma/Pinecone)
- Redis/Celery/PostgreSQL/message queues
- Plugin systems
- Multi-novel per Topic
