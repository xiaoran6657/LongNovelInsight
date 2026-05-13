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
  routers/
    health.py             — GET /api/health
    topics.py             — Topic CRUD
    documents.py          — Novel upload
    parse.py              — Chapter/chunk operations
    model_providers.py    — LLM provider config CRUD + test
    analysis_jobs.py      — Analysis job creation & status
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
    analysis_output.py
    chat.py
    job.py
    job_item.py
  services/
    storage.py            — File storage helpers
    document_service.py   — Upload/delete logic
    parser_service.py     — Chapter splitting, chunking, encoding detection
    job_service.py        — Job create, list, cancel, run
    llm_client.py         — OpenAI-compatible API client wrapper
    provider_test_service.py — Provider connection test
    prompt_loader.py      — Prompt template loading
    analysis_service.py   — Analysis pipeline orchestration
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
- The analysis pipeline runs analysis types as independent jobs. Each job calls the LLM, parses the structured output, and saves results to both SQLite and `data/analyses/`.
- Chat answers are assembled by: (1) keyword-matching the user's question against analysis outputs, (2) retrieving the top-N relevant chunks, (3) sending everything as context to the LLM.

### SQLite Database

Single file: `data/longnovelinsight.sqlite` (location configured in `config.py`).

Tables:
- `topic`
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

The backend communicates with any OpenAI-compatible chat completions API. Default: DeepSeek (`https://api.deepseek.com/v1/chat/completions`).

**Provider Configuration (stored in `model_provider` table):**
- `base_url` — API base URL
- `api_key` — user's API key (stored locally, never transmitted elsewhere)
- `model_name` — model identifier string
- `temperature` — sampling temperature for analysis vs. chat

**LLM Call Pattern:**
1. Build a system prompt describing the analysis task and output format (JSON).
2. Send chunk texts / analysis context as user messages.
3. Parse the JSON response. Validate required fields (`source_chunk_ids`, `evidence_quotes`, `confidence`).
4. Store structured output.

### Analysis Pipeline

1. **Parse** — Split novel into chapters (regex), then each chapter into overlapping chunks (fixed token window, e.g., 4000 tokens with 200 overlap).
2. **Analyze** — For each of the 6 analysis types, send relevant chunks + a structured prompt to the LLM. Analysis types are independent and run in sequence (v0.1.0 — no parallel execution needed for single-user).
3. **Store** — Save each analysis output to `data/analyses/{analysis_id}.json` and metadata to SQLite `analysis_output` table.

See [LLM_PIPELINE.md](LLM_PIPELINE.md) for detailed prompt design and output schemas.

### Job System

Long-running operations (parse novel, run analysis) are tracked as jobs.

**Job Lifecycle:** `pending` → `running` → `done` / `failed`
**Polling:** Frontend polls `GET /api/jobs/{job_id}` every 1-2 seconds during active jobs.
**Implementation:** In-process background threads (v0.1.0 — no external task queue).

## Technology Boundaries (v0.1.0)

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
