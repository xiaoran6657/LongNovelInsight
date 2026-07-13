# Architecture Decision Log

This file records accepted architecture decisions in chronological order. Append only — never overwrite or delete previous entries.

---

## 2026-05-10 — ADR-001: FastAPI + SQLModel + SQLite

**Decision:** Backend uses FastAPI as the web framework, SQLModel as the ORM, and SQLite as the database.

**Rationale:**
- FastAPI is lightweight, fast, and Python-native. No Django overhead needed for v0.1.0 scope.
- SQLModel combines SQLAlchemy and Pydantic, giving us type-safe models and validation in one package.
- SQLite is zero-config, file-based, and sufficient for a single-user local tool. No need for PostgreSQL.

**Alternatives considered:** Django + DRF (too heavy), Flask (less type-safe), raw SQLite (no validation).

---

## 2026-05-10 — ADR-002: React + TypeScript + Vite

**Decision:** Frontend uses React 18+ with TypeScript strict mode, bundled by Vite.

**Rationale:**
- React is the most widely understood frontend framework. Vite provides fast dev server and build.
- TypeScript strict mode catches type errors early, which is important for an AI-assisted project.
- No Next.js — SSR/SSG is unnecessary for a local-only single-user tool.

**Alternatives considered:** Next.js (overkill), Vue (less ecosystem), vanilla JS (no type safety).

---

## 2026-05-10 — ADR-003: One Topic = One .txt Novel in v0.1.0

**Decision:** In v0.1.0, each Topic accepts exactly one `.txt` novel file. Multi-novel Topics are deferred to v0.3.0.

**Rationale:**
- Keeps data model simple: Topic 1:1 Document.
- Multi-novel analysis (cross-referencing characters, events) significantly increases complexity.
- Users can create separate Topics for separate novels.

**Future:** v0.3.0 will relax this to Topic 1:N Document.

---

## 2026-05-10 — ADR-004: No Heavy Frameworks or Infrastructure

**Decision:** v0.1.0 uses no LangChain, Docker, Redis, Celery, PostgreSQL, or vector databases.

**Rationale:**
- This is a local-first single-user tool. A background thread for jobs is sufficient.
- LangChain adds abstraction layers that obscure LLM calls — a thin `llm_client.py` wrapper is simpler and more debuggable.
- SQLite handles the data volume comfortably for one user analyzing a few novels.
- Docker adds complexity for users who may not have it installed.
- Redis/Celery are overkill for in-process background tasks.

**Alternatives considered:** LangChain (too many abstractions), Celery + Redis (overengineered for single-user), Chroma/Pinecone (v0.1.0 doesn't do semantic search).

---

## 2026-05-10 — ADR-005: Topic.provider_id Is Optional

**Decision:** `Topic.provider_id` is nullable. Users can create a Topic without binding a provider. A provider MUST be bound before running analysis or chat.

**Rationale:**
- Decouples Topic creation from provider setup. Users can explore the UI and prepare Topics before configuring an LLM provider.
- Allows users to switch providers for the same Topic (re-bind).
- Prevents the awkward ux of "you must configure a provider before you can even create a Topic."

**Constraints:**
- `POST /api/topics` does not require `provider_id`.
- `PUT /api/topics/{topic_id}/provider` handles binding/re-binding.
- `POST /api/topics/{topic_id}/analysis` and `POST /api/chat/sessions/{session_id}/messages` return `409` if no provider is bound.
- Deleting a provider is blocked only if it is currently bound to a Topic (non-null reference).

---

## 2026-05-12 — ADR-006: Multi-Encoding Upload with UTF-8 Normalization

**Decision:** Upload accepts UTF-8-SIG / UTF-8 / GB18030 / GBK / GB2312 / UTF-16. All files are decoded with the first successful codec and re-saved as UTF-8 to `data/topics/{topic_id}/source/original.txt`.

**Rationale:**
- Chinese novels are commonly distributed in GBK or GB18030 encoding. Rejecting non-UTF-8 files would block most real-world usage.
- Normalizing to UTF-8 at upload time means all downstream code (parser, chunking, LLM prompts) can assume UTF-8 — no dual-path complexity.
- The encoding detection order prioritizes UTF-8 first, then falls back to GB-family codecs, then UTF-16. No external library (chardet) needed.
- `Document.encoding` records the actual codec used, preserving the metadata about the source file.

**Constraints:**
- `original.txt` on disk is always UTF-8.
- `Document.file_size_bytes` records the original uploaded byte count.
- `Document.char_count` records the decoded character count.
- If all codecs fail, return `400` with a user-friendly message.

---

## 2026-05-12 — ADR-007: Document Uses Independent UUID; Queries by topic_id

**Decision:** `Document.id` is an independent UUID (not set equal to `topic_id`). Queries for the current document use `select(Document).where(Document.topic_id == topic_id)`. `Document.topic_id` retains a UNIQUE constraint to enforce one-document-per-topic.

**Rationale:**
- The previous implementation set `Document.id = topic_id` at creation time, making `session.get(Document, topic_id)` the natural lookup. This conflated two distinct concepts (document identity vs. topic identity).
- An independent UUID for `Document.id` follows standard data modeling practice and allows future flexibility (e.g., document history, replacement) without PK conflicts.
- The UNIQUE constraint on `topic_id` still enforces the v0.1.0 rule of one document per topic.
- Queries via `where(topic_id == ...)` are explicit and self-documenting.

---

## 2026-05-13 — ADR-008: Unified Lowercase Enums + Model Hardening

**Decision:** All type/status strings use lowercase values via Python `StrEnum`. Field names are unified (ChatSession.title, not name). Topic.provider_id has a proper foreign key with server-side validation.

**Rationale:**
- Three separate lists (OUTPUT_TYPES, JOB_TYPES, ITEM_TYPES) had diverged: uppercase, mixed case, and inconsistent suffixes (CHARACTERS vs CHARACTER_TABLE). A single `AnalysisType` enum eliminates drift.
- Lowercase is the Python convention for `StrEnum` values and is URL/query-string friendly.
- Topic.provider_id was a plain string without FK constraint, allowing orphan references. Adding `foreign_key="model_provider.id"` enables SQL-level referential integrity.
- ChatSession had `name` in docs but `title` in code; unified to `title` for consistency.
- ModelProvider.masked_api_key is now a computed `@property`, not a separate function call scattered across routers.
- Field validators (temperature range, positive ints) added via Pydantic `model_validator` on Create schemas.

**Constraint:** Old databases with uppercase status values must be deleted (`data/longnovelinsight.sqlite`) and recreated. This is acceptable in v0.1.0 pre-launch.

---

## 2026-05-20 — ADR-009: Staged Analysis Pipeline (v0.2)

**Decision:** v0.2 replaces v0.1's per-type-per-chunk LLM calls with a staged map-reduce pipeline: local_extraction per chunk (LLM) → deterministic merge (Python) → final outputs (Python).

**Rationale:**
- v0.1 sends each chunk to the LLM 6 times (once per analysis type). v0.2 sends each chunk once, achieving ~4× token savings.
- Deterministic merge and final stages run in pure Python with no LLM cost.
- Stable IDs generated backend-side (not LLM-generated) ensure deduplication across chunks.
- The pipeline preserves evidence/source_chunk_ids/confidence tracking at every stage.

**Alternatives considered:** LLM-based merge (too expensive, unreliable), keep v0.1 6x-per-chunk (too wasteful for large novels).

---

## 2026-05-20 — ADR-010: v0.2 Backend Tables Are Independent; v1 API Preserved

**Decision:** v0.2 adds independent tables (AnalysisRun, LocalExtraction, ExtractedAtom, AnalysisArtifact) rather than modifying existing Job/JobItem tables. AnalysisOutput gains a nullable `run_id` FK. Old v1 endpoints continue to work alongside new v2 endpoints.

**Rationale:**
- v0.2's AnalysisRun lifecycle (pending → running → extraction → merge → final → succeeded/partial_success/failed) differs substantially from v0.1's Job/JobItem model.
- Independent tables avoid breaking v0.1 analysis flows and allow both pipelines to coexist.
- `AnalysisOutput.run_id` is nullable — v1 outputs have NULL, v2 outputs reference their run.
- Legacy bridge (`pipeline=v2` parameter on old endpoints) allows gradual frontend migration.

---

## 2026-05-20 — ADR-011: Hybrid Storage for Large Analysis JSON

**Decision:** Large merge/final AnalysisOutput JSON (>64KB) is stored on disk under `data/topics/{id}/artifacts/`, with metadata tracked in `analysis_artifact` table. Small JSON stays inline in SQLite. LocalExtraction content remains inline by design (single-chunk JSON rarely exceeds 64KB).

**Rationale:**
- Merge outputs for large novels can be hundreds of KB — storing these in SQLite degrades performance and bloats the database.
- A 64KB threshold balances SQLite queryability for small/typical outputs with file efficiency for large ones.
- Artifacts are tracked with SHA256 hash, size, and path for integrity and cleanup.
- Topic/Document deletion cascades to artifact file cleanup.

**Alternatives considered:** Store everything in SQLite (performance degradation), store everything on disk (loses SQL queryability for small outputs), separate API for artifact retrieval (adds complexity without benefit).

---

## 2026-05-25 — ADR-012: SQL-Level Pagination + useInfiniteQuery for Run History

**Decision:** Run history list uses SQL-level `COUNT(*) OVER()` + `OFFSET/LIMIT` pagination (not Python slicing), and the frontend uses TanStack Query's `useInfiniteQuery` with offset-based `getNextPageParam`.

**Rationale:**
- Python-slice pagination (`list_analysis_runs` → `len()` → `[offset:offset+limit]`) still loads every row from SQLite into ORM objects. For 200+ runs this is wasteful.
- Manual `page`/`offset`/`allRuns`/`dataRef`/`pageChangeRef` state management in the component had edge cases: `placeholderData` feeding stale offset data as page 0 after reset, background refetches snapping the user back to page 0, external invalidations leaving new runs invisible.
- `useInfiniteQuery` is TanStack Query's built-in primitive for cursor/offset pagination. It caches each page independently, handles invalidation by refetching from page 0, and provides `fetchNextPage`/`hasNextPage`/`isFetchingNextPage` declaratively.
- Backend `GET /topics/{id}/analysis/runs` accepts `limit` (1–200, default 50) and `offset` (≥0, default 0) with FastAPI `Query` constraints, matching the existing pattern in `parse.py`.

**Alternatives considered:** Python slicing (no real pagination), manual state accumulation (too many edge cases), `useInfiniteQuery` with cursor-based pagination (overengineered for offset-based SQL).

---

## 2026-05-25 — ADR-013: v0.3 Architecture — EPUB, FTS5, and Hybrid Retrieval

**Decision:** v0.3 adds EPUB support via Python stdlib (`zipfile` + `xml.etree.ElementTree`) for container/OPF parsing, plus `beautifulsoup4` for XHTML text extraction. Full-text search uses SQLite FTS5 (not an external search engine). Retrieval is layered: FTS5 lexical → keyword/CJK fallback → structured atom/output search, with optional semantic rerank behind a disabled-by-default feature flag.

**Rationale:**
- EPUB parsing: `zipfile` and `xml.etree.ElementTree` are stdlib and sufficient for container.xml and OPF metadata/spine parsing. `beautifulsoup4` is the lightest HTML parser that provides read-only DOM traversal without executing JS or rendering CSS. It's a single pure-Python dependency with no C extension requirement. `lxml` (faster but has native deps) and `ebooklib` (higher-level but pulls in lxml) were rejected to keep the dependency footprint minimal.
- FTS5: SQLite's built-in full-text engine requires zero additional infrastructure — no server process, no port, no config. It supports BM25 scoring and is sufficient for the project's single-user scale. Unicode61 tokenizer handles English; Chinese/CJK queries fall back to `LIKE '%keyword%'` substring matching.
- Hybrid retrieval: Layering FTS + keyword fallback + structured (ExtractedAtom/AnalysisOutput) search gives better recall than any single method. The v0.2 atom model already has canonical names, aliases, and evidence quotes ready for structured search.
- Semantic rerank (deferred): Kept as an optional v0.3.x patch behind `ENABLE_SEMANTIC_RERANK=false`. When enabled, it re-ranks top-N lexical candidates via an embedding provider's API — no local vector DB. This avoids the operational burden of Qdrant/Chroma/FAISS while leaving the door open for users who have embedding-capable providers.

**Alternatives considered:**
- `ebooklib` for EPUB parsing: handles more edge cases but depends on `lxml` (C extension, platform-specific wheels). Rejected to keep install simple.
- `lxml` directly: faster and more spec-compliant than bs4, but has native library dependencies that complicate cross-platform setup.
- Qdrant/Chroma/FAISS for retrieval: powerful but require server processes, ports, and persistence management. Rejected for v0.3 — FTS5 is simpler and sufficient for single-user local scale.
- LangChain/LlamaIndex for retrieval orchestration: add abstraction layers that obscure the retrieval pipeline. Rejected — a thin `retrieval_service.py` is more debuggable.

---

## 2026-06-03 — ADR-014: v0.4 Multi-Work Architecture

**Decision:** v0.4 introduces a Work entity between Topic and Document, enabling multi-volume story universes. Each Work can have one Document; each Topic can have many Works. Backward compatibility is maintained via default Work resolution and automatic migration of legacy single-document Topics.

**Rationale:**
- Users analyzing novel series need cross-work character tracking, relationship graphs, and timelines that span multiple volumes.
- A Topic-scoped abstraction (Topic → Work → Document) keeps the data model incremental: old single-document paths continue to work via default Work resolution.
- Deterministic cross-work aggregation (no new LLM calls) keeps costs predictable and behavior reproducible.

**Key design decisions:**
- `document.work_id` nullable FK; `document.topic_id` UNIQUE removed via table rebuild migration.
- Default Work resolution: `get_or_create_default_work()` for legacy endpoint compatibility.
- Work-scoped source file storage (`work_{id}_original.txt/epub`) to prevent cross-Work file collision.
- Scoped delete: single-document Topics get full cleanup; multi-Work Topics only delete target Work's chapters/chunks while preserving analysis data.

---

## 2026-06-03 — ADR-015: Deterministic Cross-Work Entity Resolution

**Decision:** Global entity registry built deterministically from ExtractedAtom rows across Works. No LLM calls for entity resolution. Merge strategy: same stable_id → exact canonical name + same type → alias match + same type → normalized name + same type. Type conflicts are not merged.

**Rationale:**
- LLM-based entity resolution would add cost and latency without proportional benefit at MVP scale.
- The existing v0.2 atom model already provides stable_ids, canonical names, and aliases sufficient for deterministic matching.
- Type-conflict guards (e.g., "Beijing" as character vs. location) prevent false merges.

---

## 2026-06-03 — ADR-016: v0.4 Frontend Architecture

**Decision:** Tab navigation in TopicDetailPage (Overview / Works / Entities / Graph / Timeline). No new URL routes for Work management. Character graph uses edge table MVP initially (Cytoscape planned per audit doc, deferred to v0.4.1). Timeline uses fixed-limit list.

**Rationale:**
- Tab navigation keeps existing UX intact while adding discoverability for new features.
- No new routes simplifies routing and keeps the single-Topic context consistent.
- Cytoscape deferred to avoid ~200KB bundle increase in the initial v0.4.0 release.

---

## 2026-07-12 — ADR-017: Codex-Led Repository Governance

**Decision:** `AGENTS.md` is the only stable agent rule source. Current verified state, the
prioritized queue, cross-session handoff, and durable architecture decisions are maintained in
separate versioned files under `agent/`. ChatGPT Codex owns task decomposition, agent assignment,
integration, verification, and handoff. Git publication actions always require explicit user
approval.

**Rationale:** The previous Claude-to-Codex runner duplicated rules across three files, embedded
stale version and platform assumptions, generated untracked transcripts, and granted automatic
commit behavior. Versioned, evidence-based coordination files allow a new agent or conversation
to resume without treating chat logs or historical prompts as current truth.

**Consequences:** Legacy Claude configuration, the dual-agent runner, raw runner outputs, and
historical development prompts are removed from the active workspace. Product runtime prompts
under `backend/prompts/` remain part of the application.
---

## 2026-07-12 — ADR-018: AnalysisRun Is the Authoritative Analysis Lifecycle

**Decision:** AnalysisRun and analysis_run_service are the sole supported execution lifecycle
for new analysis. The Work-scoped creation endpoint is the explicit v0.4 path; the Topic creation
endpoint is a default-Work facade over the same service. Status, cancellation, retry, and resume use
/api/analysis/runs/{run_id}. Final AnalysisOutput rows with non-null run_id are the current
result projection.

The v1 synchronous, v1 async, single-type, and Job/JobItem executors remain callable only for v0.4
compatibility and are deprecated in OpenAPI. AnalysisOutput itself is not deprecated: historical
rows with null run_id remain readable, while new product code must not create them. No Job rows or
historical outputs are rewritten as AnalysisRun records.

**Rationale:** The coexisting executors have different lifecycle, provenance, deletion, and
multi-Work behavior. Job-created outputs do not reliably link back to Job, and legacy mutators can
delete Topic-wide AnalysisOutput data. Converging new calls on AnalysisRun provides one selection,
execution, token-accounting, retry, and result-provenance contract without destroying local user
history.

**Consequences:**
- The frontend exposes only the AnalysisRun UI and removes legacy Job/v1 clients.
- Topic AnalysisRun creation resolves one deterministic default Work; it never mixes chunks across
  Works.
- Legacy execution and Job operations retain v0.4 response compatibility but are marked deprecated.
- Removing legacy routes, Job/JobItem tables, or run_id=NULL output rows requires a separately
  authorized migration/removal task. No Sunset date is declared in v0.4.
- docs/ANALYSIS_RUN_CONTRACT.md is the operational endpoint and deprecation matrix.

---

## 2026-07-12 — ADR-019: Process-Local AnalysisRun Ownership and Explicit Restart Recovery

**Decision:** The supported v0.4 backend runs as one process. analysis_run_service owns a
process-local registry that permits at most one active executor per Topic and prevents duplicate
execution of the same run. Creation, initial start, retry-failed, and resume coordinate through the
same lock; executor claims are released on normal exit and thread-start failure.

After database initialization, startup recovery marks persisted running AnalysisRuns as failed
and explicitly resumable, recording structured startup_recovery metadata. Persisted pending
runs are left unchanged. Recovery performs no LLM request; continuation requires the visible
/api/analysis/runs/{run_id}/resume action and reuses succeeded chunk extractions.

**Rationale:** Daemon threads do not survive a process restart, so leaving rows running reports
work that no executor owns. Automatically resuming would spend provider credit without a new visible
user action. A small in-process registry matches the local single-user architecture and closes
same-process start races without adding forbidden queue or locking infrastructure.

**Consequences:**
- Multiple Uvicorn workers or backend processes sharing one SQLite database are unsupported in
  v0.4; the registry is not a distributed lock.
- Startup converts only orphaned running rows. Intentionally deferred pending rows remain
  startable state and are not interpreted as interruptions.
- Retry and resume own their validation, state transition, and executor claim in the service layer.
- A future multi-process runtime would require a separately authorized database-backed lease or
  task-runner design.
---

## 2026-07-12 — ADR-020: Canonical All and Partitioned Cross-Work Scope

**Decision:** Empty work_ids denotes the canonical All scope. Scoped Work IDs are sorted,
deduplicated, validated as members of the Topic, and preserved in CrossWorkRun responses and
completed statistics.

GlobalEntity and EntityMention remain one Topic-wide canonical registry, so scoped run input does
not narrow entity rebuilding. GraphSnapshot is the only independently versioned scoped
materialization: builds replace only the same scope, unfiltered GET selects only All, and
Work-filtered GET may use the latest compatible scoped snapshot with All fallback. TimelineItem
remains one Topic-wide materialization whose scoped rebuild replaces only selected Works.

**Rationale:** The previous builders cleared Topic-wide data before every scoped build, while graph
GET selected the newest snapshot without reading scope_json. A one-Work build could therefore
silently replace the All view. Entity identity resolution also depends on cross-Work evidence and
cannot safely be partitioned without a larger schema. Partitioning graph snapshots and timeline
writes at their existing persistence boundaries preserves user-visible All data without adding new
infrastructure or speculative tables.

**Consequences:**
- Same-scope graph rebuilds are idempotent replacements; different scopes coexist.
- Filtered graph statistics describe the returned projection, not the stored source snapshot.
- Empty scoped timeline builds commit removal for selected Works only.
- Entity, graph, and timeline GET Work filters return 404 for foreign-Topic Work IDs.
- A future independently versioned entity or timeline snapshot model requires a separate migration
  decision.

---

## 2026-07-13 — ADR-021: Explicit Chat Turns and Stable Session Ordering

**Decision:** Each new user/assistant exchange shares a `turn_id` and session-local
`sequence_index`; the assistant also stores `reply_to_message_id` pointing to the user message.
Reads order by sequence, user-before-assistant role rank, timestamp, and ID. Normal send reserves
the next sequence only after obtaining SQLite's serialized writer claim. Atomic resend preserves
the logical turn and sequence while replacing its message records.

Legacy SQLite databases receive nullable additive columns and deterministic per-session backfill in
stored `created_at, rowid` order. Runtime-created pairs always populate all linkage fields. No
self-referential foreign key is added because SQLite ALTER compatibility and local repairability are
more important than a table rebuild in v0.4; service validation enforces roles and session scope.

**Rationale:** Timestamps are neither unique nor an ownership relation. Explicit linkage makes
delete and resend target the intended pair, while a shared turn sequence keeps the pair adjacent
regardless of response time.

**Consequences:**
- Deleting an assistant deletes only that message; deleting a user also deletes only its linked reply.
- Legacy rows with inherently ambiguous equal timestamps are reconstructed best-effort by row order.
- Multiple backend processes remain outside the supported v0.4 runtime boundary.

---

## 2026-07-13 — ADR-022: Ordered Replayable SQLite Migration Registry

**Decision:** Database startup first asks SQLModel to create absent current tables, then executes an
immutable ordered registry of idempotent migration functions. Each function receives the target
Engine explicitly. The runner stops on the first failure and does not record a permanent
applied-version ledger.

**Rationale:** The former `db.py` call list encoded dependencies implicitly and most functions used
the global engine, which forced tests to mutate module state. A registry makes the v0.3 locator →
v0.4 Document rebuild dependency reviewable and lets genuine old-schema fixtures exercise the same
production path. A one-time ledger would be unsafe today because Work ownership and Chat linkage
steps also repair partial or newly introduced null data on subsequent startups.

**Consequences:**
- Migration IDs and order are stable review surfaces; new migrations append rather than reorder.
- Startup may replay checks, so every migration must stay idempotent.
- Historical inline SQLite unique constraints must be inspected separately from named indexes.
- The Document table rebuild must explicitly preserve every supported Document column and restore
  the connection's prior foreign-key mode before integrity checks.
- Schema startup installs SQLite foreign-key enforcement for current and future pooled connections;
  migrations do not provide that guarantee through connection-local side effects.

---

## 2026-07-13 — ADR-023: Current-First Documentation Authorities

**Decision:** Current v0.4 documentation is divided by concern instead of repeating full API,
schema, and pipeline catalogs in multiple files. Runtime FastAPI OpenAPI is the exact HTTP schema
authority; `docs/API.md` is its complete human endpoint map. `docs/ARCHITECTURE.md` owns component,
runtime, and storage boundaries. `docs/ANALYSIS_RUN_CONTRACT.md` owns lifecycle, recovery,
provenance, and deprecation. `docs/LLM_PIPELINE.md` owns provider-call, prompt, retry, and usage
semantics. `docs/DATA_MODEL.md` owns persistence meaning and relationships.

`docs/FRONTEND_API_CONTRACT.md` describes frontend consumption, compatibility, error, and cache
rules without duplicating request/response catalogs. Root and backend READMEs link to these
authorities. Historical designs remain in release/audit documents and must be labelled historical;
they do not override current code or contracts.

**Rationale:** The previous architecture and LLM documents presented obsolete v0.1-v0.3 execution
paths before the current AnalysisRun flow, while API and frontend documents duplicated hundreds of
mutable payload lines and still omitted v0.4 Work and cross-work operations. A single owner per
concern makes drift detectable and keeps compatibility history from appearing as current design.

**Consequences:**
- Endpoint additions must update runtime OpenAPI and the human API map; frontend-only integration
  rules change only when a consumer invariant changes.
- Historical executor details stay concise in current docs and link to release history when deeper
  context is needed.
- Documentation verification compares the API map with the generated OpenAPI method/path set and
  checks local Markdown links.
