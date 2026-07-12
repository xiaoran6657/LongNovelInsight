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
├── db.py                    # SQLite engine + get_session() dependency + incremental migrations
├── pyproject.toml           # Dependencies: fastapi, uvicorn, sqlmodel, httpx, python-multipart, beautifulsoup4
├── provider_presets.py      # Provider preset catalog (DeepSeek, OpenAI, Qwen, Moonshot)
├── models/
│   ├── enums.py             # StrEnum: AnalysisType, JobType, JobStatus, AnalysisMode, AtomType
│   ├── __init__.py          # Exports all table models → SQLModel.metadata
│   ├── topic.py             # Topic (provider_id FK→model_provider)
│   ├── model_provider.py    # ModelProvider (masked_api_key @property, validators)
│   ├── topic_provider_config.py # TopicProviderConfig (topic-level config overrides)
│   ├── document.py          # Document (topic_id unique, status, encoding, file_type, metadata_json)
│   ├── chapter.py           # Chapter (chapter_index, title, char offsets, source_href, nav_order)
│   ├── chunk.py             # Chunk (text in SQLite, estimated_tokens, source_locator_json)
│   ├── analysis_output.py   # AnalysisOutput (content_json, evidence, confidence, run_id FK)
│   ├── analysis_run.py      # AnalysisRun (v2 staged pipeline lifecycle)
│   ├── local_extraction.py  # LocalExtraction (per-chunk LLM extraction, cumulative usage fields)
│   ├── extracted_atom.py    # ExtractedAtom (normalized atomic facts, stable_id)
│   ├── analysis_artifact.py # AnalysisArtifact (large JSON file storage metadata)
│   ├── retrieval_trace.py   # RetrievalTrace (v0.3: debug records per search/chat/retrieve)
│   ├── embedding_cache.py   # EmbeddingCache (v0.3: optional JSON vector cache, skeleton)
│   ├── work.py              # Work (v0.4: one novel/volume inside a Topic)
│   ├── global_entity.py     # GlobalEntity (v0.4: topic-level entity registry)
│   ├── entity_mention.py    # EntityMention (v0.4: evidence-linked mentions)
│   ├── cross_work_run.py    # CrossWorkRun (v0.4: cross-work build job tracking)
│   ├── graph_snapshot.py    # GraphSnapshot (v0.4: cached graph JSON for visualization)
│   ├── timeline_item.py     # TimelineItem (v0.4: ordered event timeline)
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
│   ├── chat.py              # session CRUD, send message with validation (two routers)
│   ├── search.py            # v0.3: POST /search (FTS5 + keyword fallback)
│   ├── retrieve.py          # v0.3: POST /retrieve (hybrid retrieval + optional trace)
│   ├── entities.py          # v0.3: GET entity evidence + similar scenes
│   ├── works.py             # v0.4: Work CRUD + work-scoped doc/parse/analysis
│   └── cross_work.py        # v0.4: entity registry + graph + timeline + cross-work run
├── services/
│   ├── llm_client.py        # OpenAICompatibleLLMClient (httpx, TransportError caught, finish_reason)
│   ├── prompt_loader.py     # Load v1 + v2 prompt templates from prompts/ dir
│   ├── analysis_service.py  # v1: run_single_analysis_output + batch-map-merge pipeline
│   ├── analysis_worker.py   # v1 worker: run_one_analysis_type (no DB, pure LLM + retry)
│   ├── job_service.py       # run_analysis_job (async parallel execution, bounded pool)
│   ├── provider_config_service.py # Effective config resolution + recommendations
│   ├── document_service.py  # upload (multi-encoding→UTF-8), delete with v2 cascade
│   ├── chat_service.py      # send_user_message (hybrid retrieval + history + LLM)
│   ├── retrieval_service.py # Keyword retrieval (stopwords, _make_excerpt, top_k=8)
│   ├── topic_service.py     # delete_topic (full cascade including v2 data), summary helpers
│   ├── storage.py           # File I/O with path traversal protection (_is_safe)
│   ├── parser_service.py    # Chapter detection (regex), chunk splitting
│   ├── provider_test_service.py # Connection test (minimal LLM call)
│   │   # ── v0.2 services ──
│   ├── stable_id_service.py       # Canonical stable ID generation (CJK-safe)
│   ├── atom_normalizer.py         # JSON → ExtractedAtom normalization (contract-strict)
│   ├── analysis_selection_service.py # Chunk meta + selection (preview/range/full/incremental) + cost estimate
│   ├── analysis_response_parser.py   # LLM JSON response parsing + validation
│   ├── local_extraction_worker.py    # Single-chunk v2 local_extraction (cumulative attempts, adaptive retry)
│   ├── analysis_run_service.py       # v2 orchestrator: create/start/cancel/retry/resume + usage recalculation
│   ├── merge_service.py              # Deterministic merge (8 types, Python-only, multi-strategy causality)
│   ├── final_output_service.py       # Merge → v0.1-compatible final AnalysisOutput
│   ├── artifact_storage_service.py   # Hybrid storage (inline + disk artifacts, 64KB threshold)
│   │   # ── v0.3 services ──
│   ├── epub_parser_service.py  # EPUB text extraction (zipfile + xml.etree + beautifulsoup4)
│   ├── source_document.py      # SourceDocument / SourceChapter dataclasses (unified TXT/EPUB)
│   ├── fts_service.py          # FTS5 rebuild/delete/search + CJK keyword fallback
│   ├── retrieval_service.py    # Hybrid retrieval (FTS + keyword + structured + outputs)
│   ├── embedding_service.py    # EmbeddingProvider skeleton + semantic_rerank stub (disabled)
│   │   # ── v0.4 services ──
│   ├── work_service.py              # Work CRUD, default Work resolution, migration helper
│   ├── cross_work_entity_service.py # Deterministic global entity registry build
│   ├── cross_work_graph_service.py  # Character relationship graph snapshot construction
│   ├── cross_work_timeline_service.py # Timeline item ordering and construction
│   └── cross_work_run_service.py    # Cross-work run orchestration and status
├── prompts/
│   ├── overview.md, characters.md, relations.md, events.md, causality.md, themes.md
│   └── local/
│       └── local_extraction.md   # v0.2+ local extraction prompt with output size limits
├── tests/                       # Unit, API, migration, and integration tests
└── scripts/
    ├── smoke_backend.py         # v0.1 smoke test (safe + --real-llm modes)
    └── smoke_v2_backend.py      # v0.2 smoke test (safe + --real-llm modes)
```

## Data Model (24 tables: 11 v0.1 + 4 v0.2 + 3 v0.3 + 6 v0.4)

```
ModelProvider  ?──*  Topic
Topic          1──1  TopicProviderConfig
Topic          1──*  Work (v0.4)
Work           1──0..1 Document
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
Topic          1──*  AnalysisArtifact (v2)
Topic          1──*  RetrievalTrace (v0.3)
ChatSession    1──*  RetrievalTrace (v0.3, optional)
Chunk          -──-  chunk_fts (v0.3, FTS5 virtual table)
EmbeddingCache 1──*  Topic (v0.3, optional, skeleton)
Topic          1──*  GlobalEntity (v0.4)
Topic          1──*  EntityMention (v0.4)
Topic          1──*  CrossWorkRun (v0.4)
Topic          1──*  GraphSnapshot (v0.4)
Topic          1──*  TimelineItem (v0.4)
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
| `WorkStatus` (v0.4) | `empty`, `uploaded`, `parsed`, `analyzed`, `error` |
| `EntityType` (v0.4) | `character`, `location`, `organization`, `concept`, `item`, `unknown` |
| `CrossWorkRunMode` (v0.4) | `full`, `entities_only`, `graph_only`, `timeline_only` |

## API Endpoints (50+)

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
| GET | `/api/provider-presets/detect?base_url=...` | Detect provider preset by base_url |

### Topic Provider Config (`/api/topics/{id}`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics/{id}/provider-config` | Get topic-level config overrides |
| PUT | `/api/topics/{id}/provider-config` | Upsert topic config (model, tokens, temp, thinking, parallelism) |
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
| POST | `/api/topics/{id}/documents/upload` | Upload .txt or .epub |
| GET | `/api/topics/{id}/documents/current` | Get current document |
| GET | `/api/topics/{id}/documents/current/metadata` | Document metadata (v0.3: EPUB parsed metadata) |
| DELETE | `/api/topics/{id}/documents/current` | Delete (cascades derived data) |

### Parse
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/parse` | Parse novel (idempotent; ?force=true to re-parse; rebuilds FTS index) |
| GET | `/api/topics/{id}/chapters` | List chapters |
| GET | `/api/topics/{id}/chunks` | List chunks (?include_text, limit, offset) |
| GET | `/api/topics/{id}/chunks/meta` | Lightweight chunk statistics (v2) |
| GET | `/api/topics/{id}/storage` | Storage usage (real chunk/analysis sizes) |

### v0.3 Search & Retrieval
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/search` | FTS5 + keyword fallback search |
| POST | `/api/topics/{id}/retrieve` | Hybrid retrieval across all sources + optional trace |
| GET | `/api/topics/{id}/chunks/{chunk_id}/locator` | Source locator + excerpt |
| GET | `/api/topics/{id}/entities/{entity_id}/evidence` | Entity evidence (atoms + chunks + outputs) |
| GET | `/api/topics/{id}/similar-scenes` | Similar scenes by chunk_id or query |

### v0.4 Works (`/api/works` and `/api/topics/{id}/works`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics/{id}/works` | List Works (ordered by series_index) |
| POST | `/api/topics/{id}/works` | Create Work |
| GET | `/api/works/{id}` | Get Work detail |
| PATCH | `/api/works/{id}` | Update Work |
| DELETE | `/api/works/{id}` | Delete Work (409 if non-empty) |
| POST | `/api/works/{id}/documents/upload` | Upload TXT/EPUB to Work |
| GET | `/api/works/{id}/documents/current` | Get Work's document |
| POST | `/api/works/{id}/parse` | Parse Work's document |
| GET | `/api/works/{id}/chapters` | List Work's chapters |
| GET | `/api/works/{id}/chunks` | List Work's chunks |
| GET | `/api/works/{id}/metadata` | Work document metadata |
| POST | `/api/works/{id}/analysis/estimate` | Read-only numeric token estimate for the same run selection |
| POST | `/api/works/{id}/analysis/runs` | Create explicit Work-scoped analysis run |
| GET | `/api/works/{id}/analysis/runs` | List analysis runs for Work |
| GET | `/api/works/{id}/analysis/outputs` | List analysis outputs for Work |

### v0.4 Cross-Work (`/api/topics/{id}`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics/{id}/entities` | List global entities (filterable) |
| GET | `/api/topics/{id}/entities/{eid}` | Get entity detail |
| GET | `/api/topics/{id}/entities/{eid}/mentions` | List entity mentions |
| POST | `/api/topics/{id}/cross-work/build` | Rebuild entity registry |
| GET | `/api/topics/{id}/graphs/characters` | Character relationship graph |
| POST | `/api/topics/{id}/graphs/build` | Rebuild graph snapshot |
| GET | `/api/topics/{id}/timeline` | Cross-work timeline (filterable) |
| POST | `/api/topics/{id}/timeline/build` | Rebuild timeline |
| POST | `/api/topics/{id}/cross-work/runs` | Create and start cross-work run |
| GET | `/api/topics/{id}/cross-work/runs` | List cross-work runs |
| GET | `/api/topics/{id}/cross-work/runs/{rid}` | Get cross-work run status |

**Cross-work scope contract:** empty work_ids means the canonical All view. Entity registry builds
are always Topic-wide. Graph snapshots coexist by normalized scope and replace only the same scope;
unfiltered graph GET never reads a scoped snapshot. Timeline scoped builds replace only selected
Works. Scoped run create/list/detail responses expose sorted, deduplicated work_ids, and Work GET
filters reject IDs outside the Topic.
### Analysis Outputs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/run` | Deprecated v1/pipeline=v2 compatibility executor |
| GET | `/api/topics/{id}/analysis/outputs` | List (?output_type, ?run_id, ?latest_only) |
| DELETE | `/api/topics/{id}/analysis/outputs` | Delete all (?run_id for targeted) |

### Authoritative Analysis Runs

See [Authoritative Analysis Run Contract](../docs/ANALYSIS_RUN_CONTRACT.md). Legacy executors remain callable in v0.4 but are OpenAPI-deprecated and have no frontend caller.

The supported runtime is one backend process. A process-local registry permits one analysis executor per Topic; startup marks orphaned running rows failed and resumable without making automatic LLM calls. Intentionally deferred pending rows are preserved.
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/works/{id}/analysis/runs` | Create explicit Work-scoped run (201) |
| POST | `/api/topics/{id}/analysis/runs` | Create run for deterministic default Work (201) |
| GET | `/api/topics/{id}/analysis/runs` | List runs for topic (paginated) |
| GET | `/api/analysis/runs/{id}` | Run status with extraction/merge/final + usage breakdown |
| POST | `/api/analysis/runs/{id}/cancel` | Cancel pending/running run |
| POST | `/api/analysis/runs/{id}/retry-failed` | Retry failed chunks, re-merge, re-final |
| POST | `/api/analysis/runs/{id}/resume` | Resume interrupted run (?retry_failed=true) |

### Analysis Jobs (deprecated compatibility)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/topics/{id}/analysis/jobs` | Deprecated: create background Job (202) |
| GET | `/api/topics/{id}/analysis/jobs` | Deprecated compatibility list |
| GET | `/api/topics/{id}/analysis/status` | Deprecated compatibility status facade |
| GET | `/api/analysis/jobs/{id}` | Deprecated Job detail |
| POST | `/api/analysis/jobs/{id}/cancel` | Deprecated Job cancellation |

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

### Analysis Modes (v0.2+)

| Mode | Behavior |
|------|----------|
| `preview` | First N chunks. Fast, low cost. |
| `range` | Specific chunk or chapter index range. |
| `full` | All chunks in the document. |
| `incremental` | Only chunks not yet extracted in a previous run. |

### v0.2 Staged Pipeline

```
POST /api/topics/{id}/analysis/runs
  → Stage 1: Local Extraction (per chunk, parallel LLM, adaptive retry)
  → Stage 2: Deterministic Merge (per type, Python-only, zero LLM cost)
  → Stage 3: Final Outputs (Python, v0.1-compatible AnalysisOutput)
```

~4× token savings vs. v0.1 per-type-per-chunk approach.
Full retry/resume/idempotency support with cumulative token accounting.

### v0.3 Token Accounting

**Cumulative across attempts:** Each extraction tracks all LLM attempts, not just the last one.
Failed retry tokens are summed into the total. `LocalExtraction` stores `reasoning_tokens`,
`prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, and `usage_unavailable_attempts`.
Run-level totals are recomputed from extraction rows after retry/resume.

**Cost estimate alignment:** `estimate_v2_analysis_cost` uses `max_output_tokens × 0.65`
per chunk, with thinking mode (1.4× buffer) and mode-based retry multiplier
(preview/incremental 1.15, full/range 1.25). Merge and final stages are confirmed
zero LLM cost (deterministic Python).

### Adaptive Retry Strategy (v0.3.1)

- Transport errors (`httpx.TransportError`) caught and wrapped as `LLMClientError`.
- `finish_reason` tracked; truncation detected when `finish_reason == "length"` or
  `completion_tokens >= max_tokens - 8`.
- Token escalation: `original → min(original × 2, 16384) → 16384`.
- Backoff: 429 errors use 15–30s; JSON truncation uses 1.5–3s; transport uses 3–6s.
- Per-attempt error re-evaluation: if attempt 1 was transport but attempt 2 shows
  JSON truncation, attempt 3 correctly escalates to `RETRY_MAX_TOKENS`.

## Tests

The default suite covers API behavior, parsing, retrieval, staged analysis, migrations,
multi-Work isolation, and cross-work aggregation. Test counts change as behavior is added, so
the current verified result is maintained in `agent/PROJECT_STATUS.md` rather than duplicated
here.

```powershell
conda run -n LongNovelInsight python -m pytest -v
conda run -n LongNovelInsight ruff check .
```

Default tests mock LLM calls and use temporary databases and data directories. Tests marked
`integration` are excluded by default and may require a live backend or external configuration.

## Key Design Decisions

- **Provider presets**: Built-in catalog of known providers (DeepSeek, OpenAI, Qwen/Alibaba, Kimi/Moonshot) with base URLs and model metadata.
- **Provider vs. Topic config**: Three-layer config resolution (Topic > Provider > Preset). Editing a Topic's config never mutates the global Provider.
- **Async parallel jobs**: `ThreadPoolExecutor` (bounded 1–6). Worker threads only call LLM; main thread writes DB.
- **Prompt-cache-friendly**: Stable prefix across LLM calls; task-specific instructions appended last.
- **Cumulative token accounting**: All LLM attempts tracked, not just the last one. Failed retry tokens summed into totals. `LocalExtraction` stores reasoning/cache/unavailable breakdown.
- **Adaptive retry**: Transport errors caught and retried. JSON truncation escalates `max_tokens` from original → `min(×2, 16384)` → `16384`. 429 uses 15–30s backoff.
- **Thinking mode**: `extra_body={"thinking": {"type": "enabled/disabled"}}`. Recommended disabled for structured extraction. Thinking mode inflates cost estimates by 1.4×.
- **Hybrid storage**: Large analysis JSON (>64KB) stored on disk; small inline in SQLite. `analysis_artifact` table tracks disk artifacts.
- **Batch-map-merge**: Two-stage pipeline for many chunks: partial per batch, then multi-level merge.
- **Causality matching**: Multi-strategy: stable_id, title, id_hints, substring containment (min 4 chars). Resolved links emit `resolved_cause_event_id` / `resolved_effect_event_id`.
- **api_key safety**: `masked_api_key` @property; all API responses exclude raw key; errors mask keys before logging.
- **Path traversal protection**: `storage._is_safe()` uses `Path.relative_to()`.
- **Hybrid retrieval (v0.3)**: FTS5 → keyword/CJK fallback → structured atoms → analysis outputs. Dedup by chunk_id, score normalization.
- **Chat grounding**: Answers include structured evidence_json; recent 6 messages for context.
- **Chat token tracking**: ChatMessage stores `prompt_tokens`, `completion_tokens`, `total_tokens`, `model_used` from LLM responses.
- **Schema migration**: `init_db()` runs incremental `ALTER TABLE ADD COLUMN` migrations. v0.3.1 adds cumulative usage columns to `local_extraction`. v0.4 adds table-rebuild migration for multi-Work support.
- **Multi-Work (v0.4)**: Topic 1→* Work, Work 1→0..1 Document. Legacy single-document Topics auto-migrate to one default Work. Work-scoped upload stores files per Work; parse/analysis cleanup scoped by document_id.
- **Cross-work entity registry (v0.4)**: Deterministic merge across Works via stable_id → exact name+type → alias match. No new LLM calls. Type conflicts are not merged.
- **Graph & timeline (v0.4)**: Derived snapshots cached in `graph_snapshot` and `timeline_item` tables. Rebuilt via cross-work run orchestration. Background thread execution avoids SQLite lock contention.
- **Work filters (v0.4)**: Search/retrieve endpoints accept optional `work_ids`. Results annotated with `work_id`, `work_title`, `series_index`. Backward-compatible when filter is absent.

## Dependencies

```toml
[dependencies]
fastapi>=0.115.0
uvicorn>=0.30.0
sqlmodel>=0.0.22
httpx>=0.27.0
python-multipart>=0.0.12
beautifulsoup4>=4.12.0

[dev]
pytest>=8.0
ruff>=0.8.0
```

## Forbidden (v0.4.0)

- Login/auth/multi-user
- Cloud sync/remote storage
- Multiple source documents per Work
- PDF parsing / OCR / DRM removal
- Docker/containerization
- LangChain/LlamaIndex
- Vector databases (Chroma/Pinecone/Qdrant/FAISS)
- Redis/Celery/PostgreSQL/message queues
- Plugin systems
- Tailwind / MUI / Ant Design / Chakra
- Redux / Zustand / MobX
