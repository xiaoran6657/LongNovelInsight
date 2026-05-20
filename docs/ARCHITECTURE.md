# LongNovelInsight v0.1.0 — Architecture

## System Overview

```
Browser (localhost:5173)
     │
     │  REST API (JSON)
     ▼
FastAPI Backend (localhost:8000)
     │
     ├── SQLite (data/longnovelinsight.sqlite)
     │
     ├── data/ directory
     │     ├── topics/{topic_id}/        — uploaded novel .txt + metadata
     │     ├── chunks/{chunk_id}.txt     — chunk text files
     │     └── analyses/{analysis_id}.json — analysis output files
     │
     └── LLM Provider (external HTTP)
           └── DeepSeek / OpenAI-Compatible API
```

## Component Breakdown

### Frontend (React + TypeScript + Vite)

A single-page application served by Vite dev server at `localhost:5173`.

**Pages / Views:**
- **Home** — list of Topics, create new Topic, storage overview, provider status.
- **Topic Detail** — upload novel, view parse results (chapters/chunks stats), trigger analysis, view analysis results, open chat.
- **Provider Settings** — add/edit/delete LLM provider configs.
- **Chat** — chat interface within a Topic.

**State Management:** React Context or lightweight state (no Redux — v0.1.0 scope does not justify it).

**API Communication:** `fetch` or `axios` to `localhost:8000/api/*`. No server-side rendering. No static generation.

### Backend (Python + FastAPI + SQLModel)

A REST API served by Uvicorn at `localhost:8000`.

**Module Structure:**
```
backend/
  main.py                — FastAPI app, CORS, lifespan
  config.py              — Settings (data dir, DB path, etc.)
  db.py                  — SQLite engine + session factory
  provider_presets.py   — Provider preset catalog (DeepSeek, OpenAI, Qwen, Moonshot)
  routers/
    health.py             — GET /api/health
    topics.py             — Topic CRUD
    documents.py          — Novel upload
    parse.py              — Chapter/chunk operations
    model_providers.py    — LLM provider config CRUD + test
    provider_presets.py   — Provider preset catalog API
    topic_provider_config.py — Per-topic config, effective config, recommendations
    analysis_jobs.py      — Async analysis job creation & status
    analysis_outputs.py   — Structured analysis run & results
    chat.py               — Chat sessions & messages
  models/
    __init__.py
    enums.py              — Shared enums (AnalysisType, JobType, etc.)
    topic.py
    document.py
    chapter.py
    chunk.py
    model_provider.py
    topic_provider_config.py — Topic-level provider config overrides
    analysis_output.py
    chat.py
    job.py
    job_item.py
  services/
    storage.py            — File storage helpers
    document_service.py   — Upload/delete logic
    parser_service.py     — Chapter splitting, chunking, encoding detection
    job_service.py        — Job create, list, cancel, async parallel run
    llm_client.py         — OpenAI-compatible API client wrapper
    provider_test_service.py — Provider connection test
    prompt_loader.py      — Prompt template loading
    analysis_service.py   — Analysis pipeline orchestration
    analysis_worker.py    — Worker: run_one_analysis_type (no DB, pure LLM + retry)
    provider_config_service.py — Effective config resolution + recommendations
    chat_service.py       — Chat context assembly & LLM call
    retrieval_service.py  — Keyword-based chunk/analysis retrieval
  prompts/
    overview.md, characters.md, relations.md, events.md, causality.md, themes.md
  tests/
    ...
```

The backend uses a flat `backend/` structure. There is no nested `backend/app/` directory. All source modules live directly under `backend/`.

**Key Design Decisions:**
- All LLM calls go through `llm_client.py` — a single thin wrapper around the OpenAI-compatible chat completions API.
- Analysis runs the 6 output types as parallel async jobs via `ThreadPoolExecutor`. Worker threads only call LLM; the main thread writes DB results.
- Provider configuration has three layers: Preset catalog (built-in) → Provider (credentials + defaults) → TopicProviderConfig (per-novel overrides). Effective config resolves Topic > Provider > Preset.
- Chat answers are assembled by: (1) keyword-matching the user's question against analysis outputs, (2) retrieving the top-N relevant chunks, (3) sending everything as context to the LLM.

### SQLite Database

Single file: `data/longnovelinsight.sqlite` (location configured in `config.py`).

Tables:
- `topic`
- `topic_provider_config`
- `document`
- `chapter`
- `chunk`
- `model_provider`
- `analysis_output`
- `chat_session`
- `chat_message`
- `job`

See [DATA_MODEL.md](DATA_MODEL.md) for full schema.

### data/ Directory

```
data/
  longnovelinsight.sqlite  — SQLite database (all data including text)
  topics/
    {topic_id}/
      source/
        original.txt       — the uploaded novel (UTF-8 normalized)
```

**v0.1.0 storage note:** For simplicity, chunk text (`Chunk.text`) and analysis JSON (`AnalysisOutput.content_json`) are stored directly in SQLite. The `data/` directory holds only uploaded novel files. Future versions (v0.2+) may migrate large text content to separate files on disk to improve database performance.

### LLM Provider

The backend communicates with any OpenAI-compatible chat completions API. Default: DeepSeek (`https://api.deepseek.com`).

**Provider Configuration Layers:**

| Layer | Source | Stores |
|-------|--------|--------|
| Preset Catalog | `provider_presets.py` | Base URLs, model metadata, thinking support, defaults |
| Provider | `model_provider` table | Credentials (api_key) + global defaults (model_name, temperature, etc.) |
| Topic Config | `topic_provider_config` table | Per-novel overrides (model, tokens, temp, thinking, parallelism) |

**Effective Config Resolution:** Topic override > Provider default > Preset default. Editing a Topic's config never mutates the global Provider.

**Built-in Provider Presets:**
- **DeepSeek** — `https://api.deepseek.com`, models: V4 Flash, V4 Pro, Chat (legacy). 1M context, JSON output, thinking mode support.
- **OpenAI** — `https://api.openai.com/v1`, model list editable.
- **Qwen / Alibaba Model Studio** — Singapore, Beijing, US Virginia, Hong Kong regions.
- **Kimi / Moonshot** — `https://api.moonshot.ai/v1`.
- **OpenAI-compatible custom** — Manual base URL, any model.

**LLM Call Pattern:**
1. Build a system prompt describing the analysis task and output format (JSON).
2. Send chunk texts / analysis context as user messages. Shared instructions and chunks form a stable prefix for prompt caching.
3. Parse the JSON response. Validate required fields (`source_chunk_ids`, `evidence_quotes`, `confidence`).
4. Store structured output.

### Analysis Pipeline

1. **Recommendation** — Inspect document size, chunk count, estimated tokens, and provider to recommend model, parallelism, and analysis mode (preview/direct/map_reduce_required).
2. **Parse** — Split novel into chapters (regex), then each chapter into overlapping chunks (fixed token window, e.g., 4000 tokens with 200 overlap).
3. **Analyze** — For each of the 6 analysis types, send selected chunks + a structured prompt to the LLM. Analysis types run in parallel via `ThreadPoolExecutor` (bounded 1-6, default 3). Workers only call LLM and return a result dataclass; the main thread writes DB rows.
4. **Store** — Save each analysis output to SQLite `analysis_output` table. Job metadata records per-type timings and token usage.

Per-type max output tokens: overview 1024, characters 3072, relations 2048, events 3072, causality 2048, themes 1536.

Retry policy: max 2 attempts per type for retryable errors (429, 5xx, timeout, rate-limit). JSON parse failures retry once with doubled max_tokens.

See [LLM_PIPELINE.md](LLM_PIPELINE.md) for detailed prompt design and output schemas.

### Analysis Modes

| Mode | Condition | Description |
|------|-----------|-------------|
| `preview` | Small/medium + limit_chunks | Subset of chunks, fast and low cost |
| `direct` | Up to ~300k chars | Full 6-type analysis via async parallel jobs |
| `map_reduce_required` | >1M chars | Blocked in v0.1 — use preview or wait for v0.2 |

### Job System

Long-running operations (parse novel, run analysis) are tracked as jobs.

**Job Lifecycle:** `pending` → `running` → `succeeded` / `partial_success` / `failed` / `cancelled`

**Analysis Job Flow:**
1. `POST /api/topics/{id}/analysis/jobs` → returns 201 with job in `pending` state.
2. Frontend polls `GET /api/topics/{id}/analysis/status` every 2-3 seconds.
3. Worker threads execute the 6 output types in parallel.
4. Main thread collects results, writes AnalysisOutput rows, updates job status.
5. If all types succeed → `succeeded`. Some fail → `partial_success` (successful outputs saved, failed types in metadata). All fail → `failed`.

**Job Metadata:** Stores per-type timings (`type_timings`), token usage (`usage_by_type` with prompt/completion/cache hit/cache miss tokens), parallelism, model name, thinking mode, and failed type details.

**Cancellation:** `POST /api/analysis/jobs/{id}/cancel` marks job cancelled. In-flight LLM calls may complete but results are discarded. Only pending/running jobs are cancellable.

**Implementation:** In-process `ThreadPoolExecutor` (v0.1.0 — no external task queue). Worker threads do NOT receive a DB session.

## Technology Boundaries (v0.1.0 / v0.2.0)

| Technology | Status |
| ---------- | ------ |
| FastAPI | Included |
| SQLModel + SQLite | Included |
| React + Vite | Included |
| LangChain | Forbidden |
| Docker | Forbidden |
| Redis / Celery | Forbidden |
| PostgreSQL | Forbidden |
| Vector Database | Forbidden |
| .epub / PDF parsing | Forbidden |

## v0.2 Staged Analysis Pipeline

v0.2 replaces v0.1's per-type-per-chunk LLM calls with a staged map-reduce design:

```
POST /api/topics/{id}/analysis/runs  (or /analysis/run?pipeline=v2)
    │
    ▼
AnalysisRun (pending → running)
    │
    ├── Stage 1: Local Extraction (parallel, per-chunk, LLM)
    │     └── LocalExtraction rows + ExtractedAtom rows
    │
    ├── Stage 2: Deterministic Merge (per-type, Python, no LLM)
    │     └── AnalysisOutput rows (output_type="merge_<type>")
    │
    └── Stage 3: Final Outputs (Python, no LLM)
          └── AnalysisOutput rows (output_type=v0.1 6 types, run_id set)
```

**Key differences from v0.1:**
- Each chunk is sent to LLM once (local_extraction), not 6 times
- Merge and final stages are deterministic Python — no LLM cost
- ~4× token savings per chunk
- Stable IDs for all entities (not LLM-generated)
- Full retry/resume/idempotency support

### v0.2 New Modules

```
backend/
  models/
    analysis_run.py        — AnalysisRun (staged pipeline lifecycle)
    local_extraction.py    — Per-chunk LLM extraction result
    extracted_atom.py      — Normalized atomic facts
    analysis_artifact.py   — Large JSON file storage pointer
  services/
    stable_id_service.py       — Canonical ID generation (CJK-safe)
    atom_normalizer.py         — JSON → ExtractedAtom normalization
    analysis_selection_service.py — Chunk selection (preview/range/full/incremental)
    analysis_response_parser.py   — LLM response JSON parsing + validation
    local_extraction_worker.py    — Single-chunk LLM extraction (pure function)
    analysis_run_service.py       — Orchestrator: create/start/cancel/retry/resume
    merge_service.py              — Deterministic merge (8 types)
    final_output_service.py       — Merge → v0.1-compatible AnalysisOutput
    artifact_storage_service.py   — Hybrid storage (inline + disk artifacts)
  routers/
    analysis_runs.py  — v2 run CRUD + retry/resume/cancel
```

### v0.2 Database Additions

| Table | Purpose |
|-------|---------|
| `analysis_run` | One row per v2 pipeline run |
| `local_extraction` | One row per chunk per run (LLM output) |
| `extracted_atom` | Normalized atomic facts per extraction |
| `analysis_artifact` | Large JSON file storage metadata |

Existing tables enhanced: `analysis_output.run_id` (nullable FK to analysis_run), `analysis_run.final_*` columns.

### v0.2 Storage Strategy

- SQLite: all structured data + small analysis JSON (≤64KB) + all LocalExtraction content
- Disk (`data/topics/{id}/artifacts/`): large merge/final AnalysisOutput JSON (>64KB)
- Artifacts tracked in `analysis_artifact` table with path/size/SHA256
- Cascade cleanup: Topic/Document deletion removes all artifacts

### v0.2 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/topics/{id}/analysis/runs` | POST | Create and start v2 run |
| `/api/topics/{id}/analysis/runs` | GET | List runs for topic |
| `/api/topics/{id}/chunks/meta` | GET | Lightweight chunk statistics |
| `/api/analysis/runs/{id}` | GET | Run status with stage summaries |
| `/api/analysis/runs/{id}/cancel` | POST | Cancel pending/running run |
| `/api/analysis/runs/{id}/retry-failed` | POST | Retry failed chunks |
| `/api/analysis/runs/{id}/resume` | POST | Resume interrupted run |

Legacy endpoints enhanced:
- `POST /analysis/run?pipeline=v2` — creates v2 run
- `GET /analysis/outputs?run_id=X&latest_only=true` — v2 output filtering
- `GET /analysis/status` — includes `latest_v2_run` and `v2_available`
