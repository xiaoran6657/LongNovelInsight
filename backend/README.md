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
├── models/
│   ├── enums.py             # StrEnum: AnalysisType, JobType, JobStatus, etc.
│   ├── __init__.py          # Exports all table models → SQLModel.metadata
│   ├── topic.py             # Topic (provider_id FK→model_provider)
│   ├── model_provider.py    # ModelProvider (masked_api_key @property, validators)
│   ├── document.py          # Document (topic_id unique, status, encoding)
│   ├── chapter.py           # Chapter (chapter_index, title, char offsets)
│   ├── chunk.py             # Chunk (text in SQLite, estimated_tokens)
│   ├── analysis_output.py   # AnalysisOutput (content_json, evidence, confidence)
│   ├── chat.py              # ChatSession, ChatMessage (+ ChatMessageCreate validation)
│   ├── job.py               # Job (job_type: parse|analysis, progress)
│   └── job_item.py          # JobItem (item_type: AnalysisType values)
├── routers/
│   ├── health.py            # GET /api/health
│   ├── topics.py            # CRUD + enriched list/detail (document, analysis_summary)
│   ├── model_providers.py   # CRUD + POST test (prefix: /api/providers)
│   ├── documents.py         # upload, get current, delete (with cascade)
│   ├── parse.py             # parse, chapters, chunks, storage
│   ├── analysis_jobs.py     # job CRUD, status, cancel (two routers)
│   ├── analysis_outputs.py  # run analysis, list/delete outputs (topic check)
│   └── chat.py              # session CRUD, send message with validation (two routers)
├── services/
│   ├── llm_client.py        # OpenAICompatibleLLMClient (httpx, 2 retries, 120s timeout)
│   ├── prompt_loader.py     # Load prompt templates from prompts/ dir
│   ├── analysis_service.py  # run_single_analysis_output + batch-map-merge pipeline
│   ├── job_service.py       # run_analysis_job (real execution, item-level status)
│   ├── document_service.py  # upload (multi-encoding→UTF-8), delete with cascade
│   ├── chat_service.py      # send_user_message (evidence retrieval + history + LLM)
│   ├── retrieval_service.py # Keyword retrieval (stopwords, _make_excerpt, top_k=8)
│   ├── topic_service.py     # delete_topic (full cascade), summary helpers
│   ├── storage.py           # File I/O with path traversal protection (_is_safe)
│   ├── parser_service.py    # Chapter detection (regex), chunk splitting
│   └── provider_test_service.py # Connection test (minimal LLM call)
├── prompts/                 # 6 prompt templates (overview, characters, relations, events, causality, themes)
├── tests/                   # 159 passing tests (see test section below)
└── scripts/
    └── smoke_backend.py     # End-to-end smoke test (safe + --real-llm modes)
```

## Data Model (10 tables)

```
ModelProvider  ?──*  Topic
Topic          1──1  Document
Document       1──*  Chapter
Chapter        1──*  Chunk
Topic          1──*  AnalysisOutput
Topic          1──*  ChatSession
ChatSession    1──*  ChatMessage
Topic          1──*  Job
Job            1──*  JobItem
```

## Enums (all lowercase StrEnum)

| Enum | Values |
|------|--------|
| `AnalysisType` | `overview`, `characters`, `relations`, `events`, `causality`, `themes` |
| `JobType` | `parse`, `analysis` |
| `JobStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| `JobItemStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| `DocumentStatus` | `uploaded`, `parsing`, `parsed`, `failed` |
| `TopicStatus` | `created`, `uploaded`, `parsed`, `analyzing`, `ready`, `failed` |

## API Endpoints (32 endpoints)

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
| POST | `/api/topics/{id}/parse` | Parse novel (idempotent) |
| GET | `/api/topics/{id}/chapters` | List chapters |
| GET | `/api/topics/{id}/chunks` | List chunks (?include_text, limit, offset) |
| GET | `/api/topics/{id}/storage` | Storage usage (real chunk/analysis sizes) |

### Analysis Outputs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/run` | Run structured analysis (?limit_chunks) |
| GET | `/api/topics/{id}/analysis/outputs` | List (?output_type filter) |
| DELETE | `/api/topics/{id}/analysis/outputs` | Delete all |

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

## Test Summary (159 tests, all passing)

| File | Tests | Key areas |
|------|-------|-----------|
| `test_documents.py` | 24 | 8 encodings, delete cascade, empty/whitespace reject, path safety |
| `test_analysis_jobs.py` | 20 | Job CRUD, item failure, cancel, no duplicates |
| `test_model_providers.py` | 16 | CRUD, default uniqueness, api_key masking |
| `test_analysis_outputs.py` | 17 | 6-type outputs, evidence, batch-merge, late characters |
| `test_parser_service.py` | 17 | Chapter detection (CN/EN), chunking, token estimation |
| `test_chat.py` | 15 | Session CRUD, send/validate, evidence, history, malformed JSON |
| `test_parse_api.py` | 13 | Parse API, chunks pagination, storage, idempotent |
| `test_topics.py` | 13 | CRUD, provider FK, document/analysis summaries, cascade delete |
| `test_retrieval_service.py` | 8 | Keyword match, stopwords filter, excerpt position, empty query |
| `test_llm_client.py` | 8 | Normal/401/network/invalid JSON/empty choices/retry/api_key leak |
| `test_model_provider_test.py` | 4 | Provider test success/404/LLM error/api_key leak |
| `test_health.py` | 1 | Health endpoint |

All tests mock LLM calls. No real external API calls in CI.

## Key Design Decisions

- **No file-per-chunk**: v0.1 stores chunk text and analysis JSON in SQLite columns. Migration to disk files planned for v0.2.
- **Sync execution**: Analysis and chat are synchronous. No background workers, Celery, or Redis.
- **Batch-map-merge**: For novels with many chunks, analysis uses a two-stage pipeline: partial analysis per batch, then multi-level merge.
- **Provider selection**: Prefers `topic.provider_id`, falls back to `is_default=True`.
- **api_key safety**: `ModelProvider.masked_api_key` @property; all API responses exclude raw `api_key`; errors use `mask_api_key()` before logging.
- **Path traversal protection**: `storage._is_safe()` uses `Path.relative_to()` instead of string `startswith`.
- **Keyword retrieval**: Substring + Chinese character overlap (filtered by ~70 stopwords) + English word overlap. No vector DB.
- **Chat grounding**: Answers must include evidence/uncertainty JSON fields; recent 6 messages included for pronoun resolution.

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
