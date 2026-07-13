# LongNovelInsight v0.4 API Guide

This guide is the human-readable map of the current `v0.4.0` API. The running FastAPI
schema is authoritative for exact request fields, response fields, validation constraints, and
status codes:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- API base URL: `http://127.0.0.1:8000/api`

All IDs are UUID strings. JSON is used except for document uploads, which use
`multipart/form-data`. Error responses use FastAPI's `{"detail": ...}` shape.

## Scope and execution rules

- A Topic is the analysis workspace. A Topic may contain multiple Works.
- A Work has at most one source Document. Work-scoped source and analysis endpoints are the
  explicit v0.4 path.
- Topic-scoped upload, parse, and AnalysisRun creation endpoints remain current compatibility
  facades and resolve the deterministic default Work. Other Topic-level source reads are legacy
  Topic views; multi-Work clients must use explicit Work endpoints when scope matters.
- `AnalysisRun` is the authoritative analysis lifecycle. See
  [ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md) for executor ownership, restart recovery,
  output provenance, and the legacy removal plan.
- Routes marked deprecated in OpenAPI remain callable for historical clients, but new frontend
  code must not use them.
- Analysis execution, provider testing, and evidence-backed chat may call the configured external
  LLM and consume provider credits. Parse, search, retrieval, estimates, and cross-work snapshot
  builds do not call the LLM.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Return backend version, Topic count, and total disk usage. |

## Topics and Works

### Topics

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/topics` | List Topics, newest first, with legacy current-document and analysis summaries. |
| `POST` | `/api/topics` | Create a Topic; an optional `provider_id` must reference an existing Provider. |
| `GET` | `/api/topics/{topic_id}` | Read one enriched Topic. |
| `PUT` | `/api/topics/{topic_id}/provider` | Bind or rebind the Topic's Provider using `{"provider_id": "..."}`. |
| `DELETE` | `/api/topics/{topic_id}` | Delete the Topic, its database records, and its local files. |

Deleting a Topic is the supported full cleanup operation. It cascades through Works, Documents,
parsed data, analysis data, retrieval traces, chat data, cross-work data, and legacy Job records.

### Work CRUD

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/topics/{topic_id}/works` | List the Topic's Works in series order. Legacy Documents without a Work are backfilled first. |
| `POST` | `/api/topics/{topic_id}/works` | Create a Work. `title` is required; subtitle, author, series index, and description are optional. |
| `GET` | `/api/works/{work_id}` | Read a Work. |
| `PATCH` | `/api/works/{work_id}` | Update supplied Work metadata fields. |
| `DELETE` | `/api/works/{work_id}` | Delete an empty Work. A Work with a Document returns `409`; delete the Topic for full cleanup. |

Work status values are `empty`, `uploaded`, `parsed`, `analyzed`, and `error`.

## Providers and model configuration

### Provider records

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/providers` | List configured OpenAI-compatible Providers. API keys are masked. |
| `POST` | `/api/providers` | Create a Provider. |
| `GET` | `/api/providers/{provider_id}` | Read a Provider. |
| `PATCH` | `/api/providers/{provider_id}` | Update supplied Provider fields. |
| `DELETE` | `/api/providers/{provider_id}` | Delete an unused Provider; returns `409` while a Topic references it. |
| `POST` | `/api/providers/{provider_id}/test` | Make a minimal real provider request and report success and latency. |

Raw API keys are accepted on create/update but are never returned. Failed provider tests return a
sanitized result without exposing the key.

### Built-in presets

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/provider-presets` | List built-in provider and model presets. |
| `GET` | `/api/provider-presets/detect?base_url=...` | Detect the preset matching a normalized base URL. |
| `GET` | `/api/provider-presets/{provider_key}` | Read one preset. |

### Topic-level effective configuration

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/topics/{topic_id}/provider-config` | Read Topic overrides, or `{"config": null}`. |
| `PUT` | `/api/topics/{topic_id}/provider-config` | Upsert optional model, token, temperature, thinking, and parallelism overrides. |
| `GET` | `/api/topics/{topic_id}/provider-config/effective` | Resolve Topic override, Provider value, and preset default into the effective configuration. |
| `GET` | `/api/topics/{topic_id}/analysis/recommendation` | Compute a recommendation from the current default Document size. |
| `POST` | `/api/topics/{topic_id}/provider-config/apply-recommendation` | Persist the current recommendation as Topic overrides. |

The effective response includes `is_ready`, `missing_fields`, and warnings. Numeric override ranges
are enforced by the API; consult OpenAPI for exact constraints.

## Source upload and parsing

TXT and EPUB are supported. TXT input is decoded from the supported UTF family or common Chinese
encodings and stored as UTF-8. EPUB input must be a valid ZIP container with
`META-INF/container.xml`; DRM removal is not supported.

### Explicit Work-scoped path

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/works/{work_id}/documents/upload` | Upload this Work's TXT/EPUB Document; returns `409` if one already exists. |
| `GET` | `/api/works/{work_id}/documents/current` | Read this Work's Document. |
| `GET` | `/api/works/{work_id}/metadata` | Read parsed source metadata as an object. |
| `POST` | `/api/works/{work_id}/parse?force=false` | Parse this Work's Document into Chapters and Chunks. |
| `GET` | `/api/works/{work_id}/chapters` | List Chapters for this Work's Document. |
| `GET` | `/api/works/{work_id}/chunks?include_text=false&limit=100&offset=0` | List this Work's Chunks in source order. |

Forcing a parse cleans only that Document's derived data when other Works exist. Work-scoped
operations do not delete another Work's source, Chunks, or analysis provenance.

### Topic compatibility facade

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/documents/upload` | Upload to the deterministic default Work. |
| `GET` | `/api/topics/{topic_id}/documents/current` | Read the legacy current Document view; use the Work route when scope matters. |
| `DELETE` | `/api/topics/{topic_id}/documents/current` | Delete the legacy current Document and its applicable derived data. |
| `GET` | `/api/topics/{topic_id}/documents/current/metadata` | Read metadata for the legacy current Document view. |
| `POST` | `/api/topics/{topic_id}/parse?force=false` | Parse the default Work's Document. |
| `GET` | `/api/topics/{topic_id}/chapters` | List the legacy Topic-wide Chapter view. |
| `GET` | `/api/topics/{topic_id}/chunks?include_text=false&limit=100&offset=0` | List the legacy Topic-wide Chunk view. |
| `GET` | `/api/topics/{topic_id}/chunks/meta` | Return lightweight legacy Topic Chunk and Chapter statistics. |
| `GET` | `/api/topics/{topic_id}/storage` | Return local database/data-directory and Topic storage estimates. |

`force=true` permits reparsing when derived analysis exists and can invalidate dependent data.
Clients should show a destructive-action warning before using it.

## Search, retrieval, and source navigation

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/search` | Search Chunks with `fts` and/or `keyword_fallback`. Optional `work_ids` narrows results. |
| `POST` | `/api/topics/{topic_id}/retrieve` | Hybrid retrieval across Chunks, atoms, and final analysis outputs. Optional `work_ids` is enforced before the final limit. |
| `GET` | `/api/topics/{topic_id}/chunks/{chunk_id}/locator` | Read a same-Topic Chunk's source locator and excerpt. |
| `GET` | `/api/topics/{topic_id}/entities/{entity_id}/evidence?limit=20` | Resolve an extracted atom by ID, stable ID, or name and return related Chunks/outputs. |
| `GET` | `/api/topics/{topic_id}/similar-scenes?chunk_id=...&query=...&limit=10` | Find similar scenes from a seed Chunk or text query. |

Search accepts a nonblank query of at most 500 characters and a result limit of 1–100. Retrieval
accepts `fts`, `keyword_fallback`, `structured`, `analysis_output`, and optional
`semantic_rerank`; at least one base retrieval method is required. `persist_trace=true` creates a
`RetrievalTrace`. Similar-scenes requires either `chunk_id` or `query`.

Scores are method-dependent ranking values, not a shared probability or guaranteed `[0, 1]`
scale.

## Authoritative analysis lifecycle

### Preflight estimate

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/works/{work_id}/analysis/estimate` | Estimate token usage for the same Work selection accepted by run creation. |

The request accepts `mode`, `requested_types`, and the same Chunk/Chapter limits and ranges as run
creation. The response reports selected Chunk counts and characters plus extraction input/output
and total token estimates. It does not create a run, write analysis state, or call the LLM. The
estimate is not a currency quote because provider pricing is not represented in configuration.

### Create and list runs

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/works/{work_id}/analysis/runs` | Create an AnalysisRun scoped to exactly one Work and optionally start it. This is the explicit v0.4 path. |
| `GET` | `/api/works/{work_id}/analysis/runs?limit=50&offset=0` | List runs whose recorded selection belongs to this Work. |
| `GET` | `/api/works/{work_id}/analysis/outputs` | List final, non-merge outputs whose AnalysisRun belongs to this Work. Historical `run_id=null` rows are excluded. |
| `POST` | `/api/topics/{topic_id}/analysis/runs` | Create a run through the deterministic-default-Work facade. |
| `GET` | `/api/topics/{topic_id}/analysis/runs?limit=50&offset=0` | List all AnalysisRuns for the Topic. |

Creation modes are `preview`, `range`, `full`, and `incremental`. `start_immediately` defaults to
true; false leaves an intentionally pending run. A Topic may have at most one pending/running
AnalysisRun in the supported single-process runtime.

### Inspect and control a run

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/analysis/runs/{run_id}` | Read run counters, Work provenance, cumulative usage, extraction rows, merge results, final outputs, and warnings. |
| `POST` | `/api/analysis/runs/{run_id}/cancel` | Request cancellation of a pending/running run. |
| `POST` | `/api/analysis/runs/{run_id}/retry-failed` | Start a background retry of failed extractions, then rerun deterministic merge/final stages. |
| `POST` | `/api/analysis/runs/{run_id}/resume?retry_failed=true` | Resume an interrupted/incomplete run, optionally including failed extractions. |

Analysis runs perform one LLM local-extraction operation per selected Chunk attempt. Atom
normalization, merge, and final projection are deterministic Python stages and make no LLM calls.
Usage is cumulative across attempts and includes reasoning/cache counters when the provider returns
them.

### Current output read model

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/topics/{topic_id}/analysis/outputs?output_type=...&run_id=...&latest_only=false` | Read final AnalysisOutput projections; merge intermediates are excluded. |
| `DELETE` | `/api/topics/{topic_id}/analysis/outputs?run_id=...` | Delete all Topic outputs or only outputs for one run when `run_id` is supplied. |

`AnalysisOutput` is current, not deprecated. A non-null `run_id` is authoritative provenance;
`run_id=null` denotes historical v1/Job-era data retained for compatibility.

## Deprecated analysis compatibility APIs

Every operation in this table is marked `deprecated: true` in OpenAPI. They may make real LLM
calls, use independent legacy executors, or have Topic-wide mutation behavior. New clients must
use AnalysisRun endpoints.

| Method | Path | Compatibility behavior |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/analysis/run` | Legacy synchronous v1 executor by default. `pipeline=v2` is a deprecated facade into AnalysisRun. |
| `POST` | `/api/topics/{topic_id}/analysis/run-async` | Legacy background v1 executor with Job/JobItem records. |
| `POST` | `/api/topics/{topic_id}/analysis/run/{output_type}` | Legacy synchronous single-type executor. |
| `POST` | `/api/topics/{topic_id}/analysis/jobs?job_type=analysis` | Create and start a legacy Job. |
| `GET` | `/api/topics/{topic_id}/analysis/jobs` | List historical Jobs. |
| `GET` | `/api/topics/{topic_id}/analysis/status` | Read combined legacy Job/output status plus a latest-AnalysisRun summary. |
| `GET` | `/api/analysis/jobs/{job_id}` | Read a historical Job and its items. |
| `POST` | `/api/analysis/jobs/{job_id}/cancel` | Cancel a legacy Job. |

The compatibility policy preserves historical records and response shapes. Removal requires
explicit scope and a migration/export plan; no v0.4 sunset date is declared.

## Chat

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/chat/sessions` | Create a session from a required `title`. |
| `GET` | `/api/topics/{topic_id}/chat/sessions` | List Topic sessions, most recently created first. |
| `GET` | `/api/chat/sessions/{session_id}/messages` | List messages in stable turn order. |
| `POST` | `/api/chat/sessions/{session_id}/messages` | Retrieve evidence and produce an assistant answer. Optional `work_ids` narrows evidence. |
| `POST` | `/api/chat/sessions/{session_id}/messages/{message_id}/resend` | Atomically replace the latest complete user/assistant exchange after regeneration. |
| `DELETE` | `/api/chat/sessions/{session_id}` | Delete a session and all its messages/traces. |
| `DELETE` | `/api/chat/sessions/messages/{message_id}` | Delete one message; deleting a user also deletes its explicitly linked assistant reply. |

Message content must be nonblank and at most 20,000 characters. Chat uses hybrid retrieval and
persists a RetrievalTrace. If retrieval finds no evidence, the service short-circuits the LLM and
returns an uncertainty warning.

Current message reads include nullable additive linkage fields:

- `turn_id`: shared by the user message and its assistant reply.
- `reply_to_message_id`: set on the assistant and points to its user message.
- `sequence_index`: stable logical turn ordering; do not infer pairs from timestamps.

`evidence_json` remains backward compatible: old rows may contain string arrays, while current
assistant messages contain structured items with source, ranking method, score, locator, and Work
metadata.

Resend requires `content` and `expected_assistant_message_id`; `work_ids` is optional. It is allowed
only for the latest complete pair. Retrieval and LLM generation finish before the short replacement
transaction, so `404`, `409`, `422`, or `502` failures leave the original exchange unchanged.

## Cross-work registry, graph, and timeline

Cross-work products are deterministic projections of persisted extracted atoms. They do not make
new LLM calls.

### Entity registry

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/cross-work/build` | Rebuild the Topic-wide entity registry and mentions. |
| `GET` | `/api/topics/{topic_id}/entities` | List registry entities with filters for type, Work, name, confidence, sorting, and pagination. |
| `GET` | `/api/topics/{topic_id}/entities/{entity_id}` | Read one registry entity. This is distinct from the extracted-atom `/evidence` route. |
| `GET` | `/api/topics/{topic_id}/entities/{entity_id}/mentions?limit=50&offset=0` | List persisted mentions for one registry entity. |

The entity registry is Topic-wide even when a CrossWorkRun has a scoped `work_ids` selection. The
selection affects graph/timeline stages, while registry entities record the Works in which they
were observed.

### Character graph snapshots

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/graphs/build` | Rebuild the canonical all-Works character graph snapshot. |
| `GET` | `/api/topics/{topic_id}/graphs/characters` | Read the latest canonical all-Works snapshot with optional graph filters. |

The graph GET accepts `work_id`, `min_confidence`, `min_weight`, `relation_type`, `limit_nodes`, and
`include_evidence`. Without `work_id`, only the canonical all-Works snapshot is selected. With a
Work filter, an applicable scoped snapshot may be used; otherwise the canonical snapshot is
filtered. Scoped builds replace only the same normalized scope and never evict the all-Works
snapshot.

### Timeline projection

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/timeline/build` | Rebuild the canonical all-Works timeline. |
| `GET` | `/api/topics/{topic_id}/timeline` | Read ordered timeline rows with Work, participant, confidence, and pagination filters. |

The timeline GET applies all supplied filters before counting and pagination. An all-Works rebuild
replaces the canonical full timeline; a scoped CrossWorkRun replaces only rows for its selected
Works.

### Cross-work orchestration runs

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/topics/{topic_id}/cross-work/runs` | Create and immediately start a background deterministic build run. |
| `GET` | `/api/topics/{topic_id}/cross-work/runs?limit=20&offset=0` | List runs and their normalized Work scopes. |
| `GET` | `/api/topics/{topic_id}/cross-work/runs/{run_id}` | Read run status, stage statistics, warnings, errors, and Work scope. |

Run modes are `full`, `entities_only`, `graph_only`, and `timeline_only`. Omitted or empty
`work_ids` means the all-Works scope; supplied IDs must belong to the Topic. Graph and timeline
builds honor the normalized scope. Entity-registry rebuilds remain Topic-wide.

## Common status codes

| Code | Meaning |
| --- | --- |
| `200` | Successful read, update, control action, or synchronous build. |
| `201` | Resource/run created. |
| `202` | Deprecated Job accepted for background execution. |
| `400` | Malformed source or legacy execution error. |
| `404` | Topic, Work, Document, Provider, message, run, or other resource not found in scope. |
| `409` | Current state prevents the operation, such as missing parsed data/provider or an active run. |
| `415` | Unsupported upload type. |
| `422` | Request validation, range, mode, type, or cross-scope failure. |
| `502` | Chat resend generation failed while the original pair was preserved. |

Use the runtime OpenAPI schema rather than this summary when generating clients or validating an
exact payload.
