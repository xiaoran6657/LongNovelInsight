# LongNovelInsight v0.4.0 — Architecture

This document defines the current v0.4 component, runtime, and storage boundaries. Historical
designs belong in [release notes](releases/) and are not part of the current contract.

## Documentation Authority

| Concern | Authority |
| --- | --- |
| Product scope and non-goals | [SPEC.md](SPEC.md) |
| Components, ownership, runtime, and storage | This document |
| Exact REST paths and schemas | Runtime OpenAPI at `/docs` or `/openapi.json`; human map in [API.md](API.md) |
| Analysis lifecycle and deprecation | [ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md) |
| LLM calls, prompts, retries, and token accounting | [LLM_PIPELINE.md](LLM_PIPELINE.md) |
| SQLite records and relationships | [DATA_MODEL.md](DATA_MODEL.md) |

## System Overview

```text
Browser SPA (localhost:5173)
        |
        | JSON REST API
        v
FastAPI process (localhost:8000)
        |
        +-- SQLite: data/longnovelinsight.sqlite
        |     +-- SQLModel application tables
        |     +-- FTS5 chunk index
        |     +-- ordered replayable startup migrations
        |
        +-- data/topics/{topic_id}/
        |     +-- source/work_{work_id}_original.{txt,epub}
        |     +-- artifacts/{artifact_type}/{owner_id}.json
        |
        +-- user-selected OpenAI-compatible provider
              +-- POST {base_url}/chat/completions
```

LongNovelInsight is a local-first, single-user application. The browser and backend run on the
same machine. Source text, derived records, provider credentials, and generated artifacts remain
local except for text intentionally sent to the configured LLM provider during connection tests,
analysis, or chat.

## Domain Ownership

```text
Topic (story universe / research workspace)
  +-- Work (novel or volume; one or more per Topic)
  |     +-- Document (zero or one TXT/EPUB source)
  |           +-- Chapter
  |                 +-- Chunk + source locator
  +-- AnalysisRun -> LocalExtraction -> ExtractedAtom
  |     +-- deterministic merge/final AnalysisOutput
  +-- ChatSession -> ChatMessage + RetrievalTrace
  +-- GlobalEntity / EntityMention
  +-- GraphSnapshot
  +-- TimelineItem
  +-- CrossWorkRun
```

Work is the source and analysis isolation boundary. Topic-level document, parse, and AnalysisRun
routes remain compatibility facades over one deterministic default Work; they must never combine
chunks from multiple Works. Cross-work materializations are Topic-owned derived views over Work
evidence.

## Frontend

The frontend is a React single-page application built with strict TypeScript and Vite. React Router
owns page navigation, TanStack Query owns server state, and plain CSS owns presentation. There is
no server-side rendering or global client-state framework.

Primary pages:

- Dashboard: health, Topics, and local storage summary.
- Providers: OpenAI-compatible provider configuration and explicit connection tests.
- Topics: Topic creation, listing, and deletion.
- Topic Detail: Works, upload/parse, analysis estimate/runs/outputs, search/retrieval, entities,
  graph, timeline, and cross-work build controls.
- Topic Chat: evidence-grounded sessions, source evidence, and provider controls.

`frontend/src/api/` contains fetch-based domain clients. `frontend/src/queryKeys.ts` is the shared
TanStack Query key factory for Topic Detail and Chat. Feature folders follow existing domains such
as `analysis`, `works`, `crossWork`, `graphs`, `timeline`, `search`, and `chat`; they are not a
plugin system.

Analysis output rendering keeps `components/AnalysisOutputCard.tsx` as a stable card/dispatch
facade. Tolerant data normalization, shared evidence primitives, and output-family renderers live
under `features/analysis/output/`, so malformed provider data remains isolated without putting all
six output families in one component.

The API base URL is `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000`. The backend permits
the Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`.

See [FRONTEND_API_CONTRACT.md](FRONTEND_API_CONTRACT.md) for frontend-specific consumption,
compatibility, and cache rules.

## Backend

The backend is one FastAPI application with a flat `backend/` module layout:

```text
backend/
  main.py                 application, CORS, startup lifespan, routers
  config.py               data/database paths, upload limit, feature flags
  db.py                   engine, sessions, database bootstrap
  migrations.py           ordered Engine-scoped migration registry
  provider_presets.py     built-in OpenAI-compatible preset metadata
  models/                 SQLModel records
  routers/                HTTP validation and response boundaries
  services/               domain operations and external HTTP calls
  prompts/                current extraction prompts plus legacy prompt assets
  tests/                  isolated unit, API, migration, and smoke coverage
```

Important service boundaries:

- `document_service.py`, `parser_service.py`, `source_document.py`, and
  `epub_parser_service.py` own TXT/EPUB ingestion and source locators.
- `analysis_run_service.py` owns the public lifecycle facade, restart recovery, and process-local
  executor registry. It delegates initial extraction/merge/final execution to
  `analysis_run_execution_service.py` and retry/resume reconstruction to
  `analysis_run_continuation_service.py`.
- `analysis_selection_service.py`, `local_extraction_worker.py`, `atom_normalizer.py`,
  `merge_service.py`, and `final_output_service.py` own the remaining authoritative analysis
  stages.
- `fts_service.py`, `retrieval_service.py`, and `chat_service.py` own evidence retrieval and chat.
- `cross_work_entity_service.py`, `cross_work_graph_service.py`,
  `cross_work_timeline_service.py`, and `cross_work_run_service.py` own deterministic cross-work
  projections.
- `artifact_storage_service.py` owns the SQLite/disk threshold for large JSON.
- `llm_client.py` is the thin direct OpenAI-compatible HTTP client; no LLM framework is used.

Routers should validate HTTP inputs and translate domain failures. Database and domain behavior
belongs in services so tests can use temporary Engines and data directories.

## Database Startup and Migrations

SQLite is stored at `data/longnovelinsight.sqlite` unless tests override configuration. Startup has
three explicit phases:

1. SQLModel creates tables that do not exist.
2. `migrations.upgrade_schema(engine)` runs the immutable `ORDERED_MIGRATIONS` registry.
3. interrupted `running` AnalysisRuns are marked failed and explicitly resumable.

Each migration receives its target Engine, is idempotent, and stops the sequence on failure. The
registry is replayable rather than tracked by a one-time version ledger because Work and Chat
migrations also repair partial or newly introduced null data. SQLite foreign keys are enabled on
every pooled connection. Startup recovery never calls the LLM and leaves intentional `pending`
runs unchanged. Startup migrations also recompute cached Topic source-byte totals and remove
persisted character-relationship snapshots whose required node/edge fields or GlobalEntity
references are invalid.

See [DATA_MODEL.md](DATA_MODEL.md) for tables and [ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md)
for recovery invariants.

## Local Storage

```text
data/
  longnovelinsight.sqlite
  topics/
    {topic_id}/
      source/
        work_{work_id}_original.txt
        work_{work_id}_original.epub
      artifacts/
        {artifact_type}/
          {owner_id}.json
```

TXT sources are normalized to UTF-8. EPUB sources are preserved as EPUB and parsed through the
source abstraction. Each Work has at most one Document row and one source file.

Structured JSON up to 64 KiB stays inline in SQLite. Larger analysis JSON is stored under the
Topic artifact directory, with an `AnalysisArtifact` record and a compact inline pointer. Storage
helpers reject paths outside `data/`. Tests that mutate state must replace both the database and
data directory with temporary locations.

## Authoritative Analysis Runtime

New analysis uses the Work-scoped AnalysisRun lifecycle:

```text
select Work chunks
       |
       v
one LLM LocalExtraction per selected chunk
       |
       v
validate and normalize ExtractedAtom rows
       |
       v
deterministic Python merge per requested output family
       |
       v
deterministic final AnalysisOutput projections
```

The default final families are overview, characters, relations, events, causality, and themes.
`worldbuilding` and `foreshadowing` are accepted atom/merge families but do not currently have the
same final UI projection contract as the default six.

Analysis execution uses process-local daemon threads and one service-owned registry. The supported
v0.4 deployment is one backend process: at most one executor owns a Topic and a run cannot be
started twice while registered. Multiple Uvicorn workers sharing one SQLite file are unsupported.

The frontend must obtain a numeric token estimate before the credit-confirmed create action. The
estimate is read-only and does not reserve capacity or guarantee billed usage. Merge and final
stages make no LLM request.

For endpoint, cancellation, retry, resume, and legacy compatibility details, see
[ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md). For prompts and retry accounting, see
[LLM_PIPELINE.md](LLM_PIPELINE.md).

## Retrieval and Chat

Parsing populates SQLite FTS5 for source chunks. Retrieval combines available lexical and
structured sources: FTS, CJK keyword fallback, extracted atoms, and analysis outputs. Candidates
are deduplicated and ranked; scores are method-dependent and are not a public probability scale.
Optional semantic reranking is disabled and its provider implementation remains a skeleton.

Chat first retrieves evidence. If no evidence is available, it returns a conservative local answer
without calling the LLM. Otherwise it sends evidence plus up to six recent messages to the selected
provider, validates the JSON answer, stores structured evidence, and persists a RetrievalTrace.

Each new user/assistant pair shares `turn_id` and `sequence_index`; the assistant stores
`reply_to_message_id`. Reads use stable session ordering. Edit/resend performs retrieval and LLM
generation outside a write transaction, then serializes and atomically replaces the expected pair
and RetrievalTrace rows after revalidation.

## Cross-Work Materializations

Cross-work entity, graph, and timeline builders are deterministic and make no LLM request.

- Empty `work_ids` means the canonical All scope.
- Work IDs are sorted, deduplicated, and validated as members of the Topic.
- GlobalEntity and EntityMention form one canonical Topic-wide registry; an entity build is not
  narrowed by a scoped run request.
- Registry rebuilds reuse a GlobalEntity ID when stable identity evidence still resolves to the
  same entity. After each rebuild, any retained graph snapshot with a node or edge reference that
  no longer resolves to the live registry is invalidated rather than served with dangling evidence
  links.
- The replayable startup migration applies the same validation to snapshots persisted by earlier
  versions, so an upgrade does not require a manual entity rebuild.
- GraphSnapshot is partitioned by normalized scope. A rebuild replaces only the same scope, and an
  unfiltered GET reads only All.
- TimelineItem is Topic-owned but Work-partitioned. A scoped rebuild replaces only selected Works.

These rules prevent a one-Work build from silently replacing the canonical All view.

## Compatibility Boundary

Legacy v1 output executors and Job/JobItem routes remain callable in v0.4 for existing local data
and clients, but are deprecated in OpenAPI and have no frontend caller. They are not the supported
path for new work. Historical `AnalysisOutput` rows with `run_id = NULL` remain readable; current
final outputs have non-null AnalysisRun provenance.

No compatibility route or migration may delete historical records merely because the path is
deprecated. Removal requires a separately authorized migration and data-handling plan.

## Fixed v0.4 Technology Boundary

- Python, FastAPI, SQLModel, SQLite.
- React, strict TypeScript, Vite, TanStack Query, plain CSS.
- Direct OpenAI-compatible HTTP; DeepSeek is the default preset, not a hard dependency.
- Local SQLite plus local files; no remote storage.
- No authentication, multi-user behavior, PDF/OCR, Docker, queues, external databases, vector
  databases, LLM frameworks, plugin systems, or new global state/UI frameworks.
