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

