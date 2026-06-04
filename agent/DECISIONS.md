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
