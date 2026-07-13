# LongNovelInsight Backend

FastAPI, SQLModel, and SQLite backend for the local-first LongNovelInsight v0.4 development line.

This file is a contributor entry point, not a duplicate API specification:

- Current component and storage boundaries: [Architecture](../docs/ARCHITECTURE.md)
- Complete human endpoint map: [API guide](../docs/API.md)
- Exact runtime schemas: `/docs` and `/openapi.json`
- Analysis lifecycle and deprecation: [AnalysisRun contract](../docs/ANALYSIS_RUN_CONTRACT.md)
- LLM behavior: [LLM pipeline](../docs/LLM_PIPELINE.md)
- Records and relationships: [Data model](../docs/DATA_MODEL.md)

## Quick Start

```powershell
conda activate LongNovelInsight
cd backend
pip install -e ".[dev]"
python -m uvicorn main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000/api`; health is
`http://127.0.0.1:8000/api/health`.

Configure provider credentials through the Providers API or frontend. Product runtime stores the
key in local SQLite, omits it from reads, and sends it only to the selected provider. It does not
read `DEEPSEEK_API_KEY`; that variable is limited to opt-in historical smoke utilities.

## Module Map

```text
backend/
  main.py                 FastAPI app, CORS, lifespan, router registration
  config.py               data/database paths, upload limit, feature flags
  db.py                   engine, sessions, database bootstrap
  migrations.py           ordered Engine-scoped migration registry
  provider_presets.py     built-in OpenAI-compatible preset metadata
  models/                 SQLModel tables and API read/write models
  routers/                HTTP validation and response boundaries
  services/               domain operations and provider HTTP calls
  prompts/                current extraction plus legacy prompt assets
  scripts/                maintained opt-in smoke utilities
  tests/                  isolated tests and integration-marked workflows
```

Key domain services:

- Source ingestion: `document_service.py`, `parser_service.py`, `source_document.py`,
  `epub_parser_service.py`.
- Current analysis lifecycle: `analysis_run_service.py` facade and executor registry,
  `analysis_run_execution_service.py` initial run, and
  `analysis_run_continuation_service.py` retry/resume.
- Current analysis stages: `analysis_selection_service.py`, `local_extraction_worker.py`,
  `atom_normalizer.py`, `merge_service.py`, `final_output_service.py`.
- Retrieval/chat: `fts_service.py`, `retrieval_service.py`, `chat_service.py`.
- Cross-work projections: `cross_work_entity_service.py`, `cross_work_graph_service.py`,
  `cross_work_timeline_service.py`, `cross_work_run_service.py`.
- Storage: `storage.py`, `artifact_storage_service.py`.
- External LLM HTTP: `llm_client.py`.

## Runtime Contracts

### Topic and Work

A Topic contains one or more Works. Each Work has at most one TXT or EPUB Document. Explicit
`/api/works/{work_id}` upload, parse, and analysis routes are the v0.4 path. Topic-level equivalents
remain compatibility facades over a deterministic default Work.

### Analysis

AnalysisRun is the only supported execution lifecycle for new code. It performs one LLM local
extraction per selected Chunk attempt, persists normalized atoms, and generates merge/final
AnalysisOutput projections in deterministic Python.

The supported backend is one process. A process-local registry allows one AnalysisRun executor per
Topic. Startup marks orphaned `running` runs failed and resumable without making an LLM request;
intentional `pending` runs remain pending.

The v1 synchronous/async/single-type and Job/JobItem routes remain OpenAPI-deprecated compatibility
paths. Do not add frontend callers or use them for new features.

### Chat

Chat uses hybrid local evidence retrieval before an LLM request. Empty retrieval returns a
conservative response without calling the provider. Current message pairs use `turn_id`,
`reply_to_message_id`, and `sequence_index` for explicit linkage and stable ordering.

Edit/resend generates outside a write transaction, then serializes, revalidates, and atomically
replaces the expected pair and RetrievalTrace rows. A failed generation preserves the original
pair.

### Cross-work

Entity, graph, and timeline builders are deterministic and do not call the LLM. Empty Work scope
means canonical All. Entity records are Topic-wide, graph snapshots are partitioned by normalized
scope, and scoped timeline rebuilds replace only selected Works.

## Database and Files

Default local state:

```text
data/
  longnovelinsight.sqlite
  topics/{topic_id}/
    source/work_{work_id}_original.{txt,epub}
    artifacts/{artifact_type}/{owner_id}.json
```

Startup first creates absent SQLModel tables, then replays `ORDERED_MIGRATIONS`. Every migration
accepts its target Engine, is idempotent, and stops the registry on failure. The registry has no
permanent applied-version ledger because Work and Chat migrations also repair partial/backfilled
rows. SQLite foreign keys are enabled for every pooled connection.

Structured analysis JSON up to 64 KiB stays inline. Larger payloads use a local artifact file plus
an AnalysisArtifact record and inline pointer. Storage helpers reject path traversal outside
`data/`.

## Verification

```powershell
cd backend
conda run -n LongNovelInsight ruff check .
conda run -n LongNovelInsight ruff format --check .
conda run -n LongNovelInsight python -m pytest -v
```

The default test suite must use temporary database/data paths and mock the LLM boundary. Tests
marked `integration` remain opt-in when they represent historical or live-server workflows. The
default-safe v0.4 Work smoke is `tests/test_v04_integrated_smoke.py`; it exercises upload, parse,
AnalysisRun extraction/merge/final, output reads, and cleanup while mocking only the LLM extraction
call.

Do not run `scripts/integration_smoke.py` with provider credentials unless a real LLM call is the
explicit intent.

## Fixed v0.4 Boundary

Do not introduce authentication, multi-user behavior, multiple Documents per Work, PDF/OCR,
Docker, external databases, queues, vector databases, LangChain/LlamaIndex, plugin systems, or
remote storage. See [AGENTS.md](../AGENTS.md) for the complete engineering rules.
