# Backend v0.4 Step 0 — Audit & Implementation Plan

> Generated 2026-06-03 from current `main` (post v0.3.1).

## 1. Current Schema Summary

### 1.1 Existing tables (18)

| # | Table | Key FKs | Records |
|---|-------|---------|---------|
| 1 | `topic` | `provider_id` → `model_provider` | 1 Topic = 1 current Document |
| 2 | `model_provider` | — | LLM provider config |
| 3 | `topic_provider_config` | `topic_id` (unique), `provider_id` | Per-topic overrides |
| 4 | `document` | `topic_id` (unique) | Uploaded TXT/EPUB |
| 5 | `chapter` | `topic_id`, `document_id` | Parsed chapters |
| 6 | `chunk` | `topic_id`, `document_id`, `chapter_id` | Parsed chunks |
| 7 | `analysis_output` | `topic_id`, `job_id`, `run_id` (nullable) | Analysis results |
| 8 | `analysis_run` | `topic_id`, `job_id` (nullable) | v2 pipeline run |
| 9 | `local_extraction` | `run_id`, `topic_id`, `chunk_id` | Per-chunk extraction |
| 10 | `extracted_atom` | `run_id`, `topic_id`, `local_extraction_id`, `chunk_id` | Normalized atoms |
| 11 | `analysis_artifact` | `topic_id` | Large JSON storage |
| 12 | `chat_session` | `topic_id` | Chat sessions |
| 13 | `chat_message` | `session_id` | Chat messages |
| 14 | `job` | `topic_id` | v1 job tracking |
| 15 | `job_item` | `job_id` | v1 job items |
| 16 | `retrieval_trace` | `topic_id`, `session_id` (nullable) | Retrieval debug |
| 17 | `embedding_cache` | `topic_id` | Skeleton cache |
| 18 | `chunk_fts` | (FTS5 virtual table) | Full-text index |

### 1.2 Key constraint: `document.topic_id` UNIQUE

`Document.topic_id` has a UNIQUE constraint. This enforces 1 Document per Topic at the
database level. v0.4 must relax this: the uniqueness should move to `(work_id, topic_id)`
conceptually, while maintaining backward compatibility for legacy queries.

### 1.3 Ownership chain

```
Topic → Document → Chapter → Chunk
Topic → AnalysisRun → LocalExtraction → ExtractedAtom
Topic → AnalysisOutput
Topic → ChatSession → ChatMessage
```

Everything flows through `topic_id`. v0.4 must add a `work_id` branch without breaking
the existing `topic_id` path.

## 2. Files to Modify

### 2.1 New files (models)

| File | Purpose |
|------|---------|
| `backend/models/work.py` | `Work` model + `WorkCreate` / `WorkRead` schemas |
| `backend/models/global_entity.py` | `GlobalEntity` model |
| `backend/models/entity_mention.py` | `EntityMention` model |
| `backend/models/cross_work_run.py` | `CrossWorkRun` model |
| `backend/models/graph_snapshot.py` | `GraphSnapshot` model |
| `backend/models/timeline_item.py` | `TimelineItem` model |

### 2.2 New files (routers)

| File | Purpose |
|------|---------|
| `backend/routers/works.py` | Work CRUD, Work-scoped upload/parse/analysis |
| `backend/routers/cross_work.py` | Cross-work run + entity registry + graph + timeline endpoints |

### 2.3 New files (services)

| File | Purpose |
|------|---------|
| `backend/services/work_service.py` | Work CRUD, default Work resolution, migration helper |
| `backend/services/cross_work_entity_service.py` | Deterministic global entity registry build |
| `backend/services/cross_work_graph_service.py` | Character relationship graph snapshot construction |
| `backend/services/cross_work_timeline_service.py` | Timeline item ordering and construction |
| `backend/services/cross_work_run_service.py` | Cross-work run orchestration and status |

### 2.4 Modified files

| File | Changes |
|------|---------|
| `backend/models/__init__.py` | Add new model exports |
| `backend/models/enums.py` | Add `WorkStatus`, `EntityType`, `CrossWorkRunMode` enums |
| `backend/models/document.py` | Add `work_id` nullable FK column |
| `backend/db.py` | Add `_migrate_v04_work_tables()` migration |
| `backend/routers/documents.py` | Support `work_id`-scoped upload; legacy endpoint → default Work |
| `backend/routers/parse.py` | Support `work_id`-scoped parse/chapters/chunks; legacy → default Work |
| `backend/routers/analysis_runs.py` | Accept optional `work_id`; scope chunk selection to Work's chunks |
| `backend/services/document_service.py` | `work_id` parameter; upload checks Work existence + 1-doc-per-Work constraint |
| `backend/services/parser_service.py` | **Critical:** `parse_novel()` reads document by `work_id` not `topic_id`; `_persist_parse()` deletes chapters/chunks by `document_id` not `topic_id`; TXT/EPUB source path resolution uses Work's document |
| `backend/services/analysis_selection_service.py` | `work_id` filter for chunk selection |
| `backend/services/analysis_run_service.py` | `work_id` field in run config; filter chunks by Work |
| `backend/services/topic_service.py` | Cascade delete extended to Work + cross-work tables |
| `backend/services/storage.py` | Work-aware directory layout (optional; v0.4 can keep topic-level dirs) |
| `backend/main.py` | Register new routers |

### 2.5 New tests

| File | Purpose |
|------|---------|
| `backend/tests/test_works.py` | Work CRUD, default Work resolution, migration |
| `backend/tests/test_cross_work_entity.py` | Entity merge, alias matching, type conflicts |
| `backend/tests/test_cross_work_graph.py` | Graph construction, filters, empty data |
| `backend/tests/test_cross_work_timeline.py` | Timeline ordering, filters, source locators |
| `backend/tests/test_cross_work_run.py` | Run orchestration, status transitions |
| `backend/tests/test_v04_migration.py` | Legacy DB migration to default Work |
| `backend/tests/test_v04_compatibility.py` | v0.3 endpoints still work post-migration |

### 2.6 Function-level modification targets

| File | Function / Class | Change |
|------|-----------------|--------|
| `document_service.py` | `upload_document(topic_id, ...)` | Accept optional `work_id`; resolve default Work if not provided; check 1-doc-per-Work |
| `document_service.py` | `_upload_txt(topic_id, ...)` | Accept `work_id`; set `document.work_id` on creation |
| `document_service.py` | `_upload_epub(topic_id, ...)` | Accept `work_id`; set `document.work_id` on creation |
| `document_service.py` | `_get_doc_by_topic(topic_id, session)` | Rename to `_get_doc_by_work(work_id, session)`; query by `work_id` |
| `document_service.py` | `get_current_document(topic_id, ...)` | Resolve default Work, then query by `work_id` |
| `document_service.py` | `delete_current_document(topic_id, ...)` | Resolve default Work; delete by Work's document; scope derived-data cleanup to Work |
| `document_service.py` | `_delete_document_derived_data(topic_id, ...)` | Accept `work_id`; scope chapter/chunk/atom/run deletion to Work's document, not whole Topic |
| `parser_service.py` | `parse_novel(topic_id, ...)` | **Critical:** Accept `work_id`; read document by `work_id` not `topic_id`; source file path uses Work's document `stored_filename` |
| `parser_service.py` | `_persist_parse(topic_id, ...)` | **Critical:** Delete existing chapters/chunks by `document_id` (not `topic_id`); write new chapters/chunks with correct `document_id` |
| `parser_service.py` | TXT source reader | Read `original.txt` from Work's document path, not Topic-level default |
| `parser_service.py` | EPUB source reader | Read `original.epub` from Work's document path; EPUB metadata written to Work's document `metadata_json` |
| `analysis_selection_service.py` | `get_chunks_meta(topic_id, session)` | Accept optional `work_id`; filter chunks by `document_id` from Work |
| `analysis_selection_service.py` | `select_chunks_for_analysis(topic_id, ...)` | Accept optional `work_id`; scope chunk query to Work's document |
| `analysis_run_service.py` | `create_analysis_run(topic_id, ...)` | Accept optional `work_id`; store in `chunk_selection_json`; scope chunk list to Work |
| `analysis_run_service.py` | `_execute_run_impl(run_id, engine)` | Load chunks scoped to `work_id` from `chunk_selection_json` |
| `topic_service.py` | `delete_topic(topic_id, session)` | Add cascade for `entity_mention`, `global_entity`, `graph_snapshot`, `timeline_item`, `cross_work_run`, `work` |
| `routers/documents.py` | `upload(topic_id, ...)` | Accept optional `work_id` query param or body field; pass to service |
| `routers/documents.py` | `get_current(topic_id, ...)` | Resolve default Work via `work_service` |
| `routers/parse.py` | `parse(topic_id, ...)` | Accept optional `work_id`; pass to `parser_service.parse_novel()` |
| `routers/parse.py` | `list_chapters(topic_id, ...)` | Accept optional `work_id`; scope query |
| `routers/parse.py` | `list_chunks(topic_id, ...)` | Accept optional `work_id`; scope query |
| `routers/parse.py` | `get_chunks_meta(topic_id, ...)` | Accept optional `work_id`; pass to service |
| `routers/analysis_runs.py` | `create_run(topic_id, ...)` | Accept optional `work_id` in `CreateRunRequest` |
| `routers/analysis_runs.py` | `list_runs(topic_id, ...)` | Accept optional `work_id` filter |

## 3. Key Design Decisions

### 3.1 `document.work_id` — table rebuild to remove `topic_id` UNIQUE

**Decision:** Replace the `topic_id` UNIQUE constraint with a nullable `work_id`
unique index. This requires a full table rebuild because SQLite cannot ALTER TABLE
to drop a column-level UNIQUE constraint that was created as an implicit index.

**Migration steps:**

**Precondition:** The `work` table must exist before the document table rebuild
(because `document_new.work_id` references `work.id`). The `work` table is created
via `SQLModel.metadata.create_all` earlier in the same migration function.

```sql
-- Step 0: Disable FK enforcement BEFORE starting the transaction.
-- IMPORTANT: PRAGMA foreign_keys does NOT take effect inside a transaction
-- in SQLite. It must be set before BEGIN.
PRAGMA foreign_keys = OFF;

BEGIN;

-- Step 1: Create replacement table. Removes topic_id UNIQUE, adds work_id FK.
-- All other columns and the topic_id → topic FK are preserved exactly.
CREATE TABLE document_new (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topic(id),
    work_id TEXT REFERENCES work(id),   -- nullable; unique-enforced by partial index later
    original_filename TEXT NOT NULL DEFAULT '',
    stored_filename TEXT NOT NULL DEFAULT 'original.txt',
    file_type TEXT NOT NULL DEFAULT 'txt',
    content_type TEXT,
    encoding TEXT NOT NULL DEFAULT 'utf-8',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    char_count INTEGER NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL DEFAULT '',
    metadata_json TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Step 2: Copy all existing data with explicit column names.
-- All legacy documents get work_id = NULL.
INSERT INTO document_new (
    id, topic_id, work_id, original_filename, stored_filename,
    file_type, content_type, encoding, file_size_bytes, char_count,
    storage_path, metadata_json, status, created_at, updated_at
)
SELECT
    id, topic_id, NULL, original_filename, stored_filename,
    file_type, content_type, encoding, file_size_bytes, char_count,
    storage_path, metadata_json, status, created_at, updated_at
FROM document;

-- Step 3: Swap tables
DROP TABLE document;
ALTER TABLE document_new RENAME TO document;

COMMIT;

-- Step 4: Re-enable FK enforcement AFTER the transaction commits.
-- PRAGMA foreign_keys can now take effect.
PRAGMA foreign_keys = ON;

-- Step 5: Verify integrity. Must return zero rows.
-- If any FK violation is found, the migration has failed and must be
-- investigated (possible causes: orphan topic_id, work_id referencing
-- a nonexistent work row).
PRAGMA foreign_key_check;
```

**Python-level data migration (idempotent, after table swap):**
For each Topic with a Document, if no Work exists for that Topic:
create a default Work and `UPDATE document SET work_id = <work.id>
WHERE id = <doc.id>`.

**Partial unique index (after data migration):**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS ix_document_work_id
ON document(work_id) WHERE work_id IS NOT NULL;
```
Multiple NULLs allowed, but at most one non-NULL document per `work_id`.

**Foreign key safety notes:**
- `PRAGMA foreign_keys = OFF` is set **before** the `BEGIN` statement.
  SQLite does not apply `PRAGMA foreign_keys` changes within an active
  transaction; it must be set at the connection level outside any
  transaction. Ditto for `PRAGMA foreign_keys = ON` after `COMMIT`.
- The table rebuild executes inside a single `BEGIN/COMMIT` transaction
  with FK enforcement suspended.
- `PRAGMA foreign_key_check` runs after FK enforcement is re-enabled.
  It must return zero rows. If any violation is detected, the migration
  has failed (possible causes: orphan `topic_id`, `work_id` referencing
  a nonexistent work row).
- `chapter.document_id → document.id` and `chunk.document_id →
  document.id` FKs survive because `document.id` values are preserved
  identically in the copy.
- `document_new.topic_id` has an explicit `REFERENCES topic(id)` FK,
  matching the constraint on the old `document` table.
- `document_new.work_id` has `REFERENCES work(id)` — the `work` table
  must be created (Step 2 below) before this table rebuild runs.

**Idempotency:** Check for existence of `ix_document_work_id` index
before rebuilding. If the index already exists, skip the table rebuild.
The data migration checks for existing default Works before creating
new ones — safe to run multiple times.

**Why `ALTER TABLE ADD COLUMN` is insufficient:** SQLite's UNIQUE
constraint on `topic_id` is enforced by an auto-index that cannot be
dropped via `DROP INDEX`. The only portable way to remove it is a
table rebuild. This is a one-time migration that preserves all data,
FKs, and column types.

**Service-layer enforcement after migration:**
- `document_service.upload_document()` checks `session.exec(select(Document).where(Document.work_id == work_id)).first()` before allowing upload; rejects with 409 if a Document already exists for that Work.
- Legacy upload endpoint (topic-scoped) resolves default Work first, then delegates.
- `_get_doc_by_topic()` renamed to `_get_doc_by_work(work_id, session)`; legacy callers use default Work resolution.

### 3.2 Default Work resolution

**Decision:** A single module-level function `get_or_create_default_work(topic_id, session)`
that:
1. Lookups Work with `series_index = 1` (or oldest) for the topic.
2. If no Work exists but a legacy Document exists: create a default Work and assign
   `document.work_id`.
3. If no Work and no Document: raise 404 or return None depending on caller.

This function is called by all legacy endpoints (`/topics/{id}/documents/current`,
`/topics/{id}/parse`, etc.) to transparently resolve the default Work.

### 3.3 Entity resolution is deterministic

**Decision:** No new LLM calls for entity resolution in v0.4.0.

Resolution pipeline:
1. Collect all `ExtractedAtom` rows with `atom_type = "character"` across all Works
   within the Topic.
2. For each atom, extract `canonical_name`, `stable_id`, and any `aliases` from
   `content_json`.
3. Match by: exact stable_id → exact canonical_name → alias match → normalized name
   match (lowercase, strip, collapse whitespace).
4. Type conflicts (same normalized name, different `entity_type`) → do not merge, emit
   warning.
5. Build `GlobalEntity` rows and `EntityMention` rows linking back to source atoms,
   chunks, and analysis outputs.

### 3.4 Graph snapshots are derived, not source of truth

**Decision:** `graph_snapshot` stores pre-computed JSON for frontend rendering.
It is regenerated on each cross-work build run. No incremental update in v0.4.0.

Character relationship graph edges derived from:
1. Relation atoms (`atom_type = "relation"`) with `character_a`/`character_b`.
2. Event co-occurrence (two characters in same event's `participants` list).
3. Causality participants as weak signal.

### 3.5 Timeline ordering

**Decision:** `sequence_index` = `work.series_index * 1_000_000 + chunk_index`.
This gives a stable, sortable float that preserves Work order and within-Work chunk
order. For Works without `series_index`, default to 1.

## 4. Compatibility Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `document.topic_id` UNIQUE constraint removal | High | Use table-rebuild migration; test with real DB before release |
| Legacy endpoints break when Work exists but Document doesn't | Medium | `get_or_create_default_work` returns 404 with clear message |
| Analysis runs scoped to wrong chunks after Work migration | Medium | `chunk_selection_json` stores `work_id`; old runs preserve `topic_id`-based selection |
| Cross-work entity merge false positives | Medium | Conservative thresholds (min 4 chars normalized); type-conflict guard; deterministic only |
| Cascade delete misses new v0.4 tables | Low | Add explicit delete steps for `entity_mention`, `global_entity`, `graph_snapshot`, `timeline_item`, `cross_work_run`, `work` |
| v0.3 search/retrieve/chat evidence continue to use `topic_id` | Low | Evidence cards gain optional `work_id`/`work_title` fields; backward-compatible |

## 5. Migration Plan

### 5.1 `_migrate_v04_work_tables()` in `db.py`

```python
def _migrate_v04_work_tables() -> None:
    """v0.4 multi-Work schema migration. Idempotent — safe to run multiple times."""

    # Guard: skip if already migrated (check for ix_document_work_id index)

    # 1. Create work table FIRST (document rebuild references work.id FK)
    #    Uses SQLModel.metadata.create_all(tables=[Work.__table__])

    # 2. Document table rebuild (remove topic_id UNIQUE, add work_id FK)
    #    Executes the SQL from §3.1:
    #    - PRAGMA foreign_keys = OFF (before BEGIN)
    #    - BEGIN
    #    - CREATE TABLE document_new (... REFERENCES topic(id), REFERENCES work(id))
    #    - INSERT INTO document_new (explicit columns) SELECT ... FROM document
    #    - DROP TABLE document
    #    - ALTER TABLE document_new RENAME TO document
    #    - COMMIT
    #    - PRAGMA foreign_keys = ON (after COMMIT)
    #    - PRAGMA foreign_key_check (must return 0 rows)
    #    Executed via raw SQL with engine.connect()

    # 3. Create remaining new tables (idempotent via CREATE TABLE IF NOT EXISTS):
    #    global_entity, entity_mention, cross_work_run,
    #    graph_snapshot, timeline_item
    #    Uses SQLModel.metadata.create_all(tables=[...]) pattern from
    #    _migrate_analysis_artifact, _migrate_retrieval_trace, etc.

    # 4. Create partial unique index on document(work_id) WHERE work_id IS NOT NULL
    #    CREATE UNIQUE INDEX IF NOT EXISTS ix_document_work_id ...

    # 5. Python-level data migration (idempotent):
    #    For each Topic with a Document and no Work:
    #      create default Work (title from doc filename / topic name)
    #      UPDATE document SET work_id = <work.id>
    #    Uses Session(engine) for ORM access (same pattern as FTS rebuild)
```

### 5.2 Step-by-step migration execution order

1. **Create `work` table** — `SQLModel.metadata.create_all(engine, tables=[Work.__table__])`.
   Must be created **before** the document table rebuild because
   `document_new.work_id REFERENCES work(id)`. Uses the existing
   `_migrate_analysis_artifact` / `_migrate_retrieval_trace` pattern.
2. **Document table rebuild** — raw SQL transaction via `engine.connect()`
   (see §3.1 SQL). Removes `topic_id` UNIQUE, adds `work_id TEXT`
   with FK to `work(id)`. Executes in this order:
   `PRAGMA foreign_keys = OFF` → `BEGIN` → CREATE/INSERT/DROP/RENAME
   → `COMMIT` → `PRAGMA foreign_keys = ON` → `PRAGMA foreign_key_check`.
3. **Create remaining new tables** — `global_entity`, `entity_mention`,
   `cross_work_run`, `graph_snapshot`, `timeline_item`.
4. **Partial unique index** — `CREATE UNIQUE INDEX IF NOT EXISTS
   ix_document_work_id ON document(work_id) WHERE work_id IS NOT NULL`.
5. **Data migration** — Python/ORM. Creates default Works for legacy
   Topics with Documents. Backfills `document.work_id`.
6. **Verification** — `PRAGMA foreign_key_check` returns 0 rows
   (re-verified after data migration). Log count of migrated Topics.

This function is called by `init_db()` after all existing migrations.
The guard check (step 0) ensures it's skipped if already applied.

## 6. Test Strategy

### 6.1 Migration tests (`test_v04_migration.py`)

- Legacy Topic + Document → default Work created, `document.work_id` set.
- Legacy Topic with no Document → no Work created.
- Migration idempotent (run twice, no duplicate Works).
- v0.3 document/chapter/chunk queries still work after migration.

### 6.2 Work API tests (`test_works.py`)

- Create/list/update Work.
- `POST /api/topics/{id}/works` with valid body → 201.
- `GET /api/topics/{id}/works` returns ordered list.
- `PATCH /api/works/{id}` updates title/author/series_index.
- `DELETE /api/works/{id}` on empty Work → 200; on analyzed Work → 409.
- Default Work resolution: topic with legacy doc → GET returns one Work.

### 6.3 Work-aware upload/parse/analysis tests

- `POST /api/works/{id}/documents/upload` accepts TXT/EPUB.
- Upload to Work that already has a document → 409.
- `POST /api/works/{id}/parse` parses Work's document.
- `POST /api/works/{id}/analysis/runs` creates run scoped to Work's chunks.
- Legacy endpoints (`/topics/{id}/documents/upload`) target default Work.

### 6.4 Cross-work entity tests (`test_cross_work_entity.py`)

- Same character name across two Works → merged into one GlobalEntity.
- Alias match merges.
- Type conflict (name X as character + name X as location) → does not merge, emits
  warning.
- Mentions link back to correct Work and chunk.
- Empty topic (no atoms) → empty entity list, no error.

### 6.5 Graph tests (`test_cross_work_graph.py`)

- Character relation graph returns nodes + edges from relation atoms.
- `work_id` filter limits to one Work's data.
- `min_confidence` and `min_weight` filters work.
- Empty data returns `{"nodes": [], "edges": []}` not an error.

### 6.6 Timeline tests (`test_cross_work_timeline.py`)

- Events produce ordered timeline items.
- `sequence_index` stable across rebuilds.
- `work_id` filter works.
- `participant_entity_id` filter works.
- Source locators included in response.

### 6.7 Compatibility tests (`test_v04_compatibility.py`)

- All v0.3 endpoints return expected shapes (200/404/409 etc.).
- Search/retrieve/chat continue to work.
- Structured chat evidence unchanged.

## 7. Proposed Step Order

| Step | Description | Estimated new files | Modified files |
|------|-------------|---------------------|----------------|
| **1** | Schema + Migration | 6 models, 1 migration | `__init__.py`, `enums.py`, `document.py`, `db.py` |
| **2** | Work CRUD + Default Work | `work_service.py`, `routers/works.py` | `main.py` |
| **3** | Work-Aware Upload/Parse | `routers/works.py` (extend) | `document_service.py`, `parser_service.py` (**critical**), `routers/documents.py`, `routers/parse.py` |
| **4** | Work-Scoped Analysis | — | `analysis_run_service.py`, `analysis_selection_service.py`, `routers/analysis_runs.py` |
| **5** | Entity Registry Builder | `cross_work_entity_service.py` | — |
| **6** | Graph Snapshot Builder | `cross_work_graph_service.py` | — |
| **7** | Timeline Builder | `cross_work_timeline_service.py` | — |
| **8** | Cross-Work Run API | `cross_work_run_service.py`, `routers/cross_work.py` | `main.py` |
| **9** | Search/Retrieve Scope Filters | — | `retrieval_service.py`, `routers/search.py`, `routers/retrieve.py` |
| **10** | Tests + Docs | 7 test files | `topic_service.py` (cascade), `CLAUDE.md`, READMEs |

Steps 1–4 must be sequential (Work must exist before upload/parse/analysis).
Steps 5–7 can be parallelized after Step 4.
Step 8 depends on Steps 5–7.
Step 9 is optional for MVP.
Step 10 runs throughout.

## 8. Acceptance Criteria (this step)

- [x] This document exists at `docs/v0.4/backend-step0-audit.md`.
- [x] All existing tables and their relationships are documented.
- [x] Exact new files to create are listed with module names.
- [x] Exact existing files to modify are listed with specific changes.
- [x] Compatibility risks are identified with mitigations.
- [x] Migration plan is documented step-by-step.
- [x] Test strategy covers all new functionality plus backward compatibility.
- [x] Step order is defined with dependencies.

## 9. Test Baseline (pre-v0.4)

Command:
```bash
cd backend && conda run -n LongNovelInsight python -m pytest -q
```

Result:
```
631 passed, 6 deselected in 69.56s
```

All existing tests pass. No behavior files modified in this step. Ruff check is clean.
This baseline must be re-verified after each v0.4 step.

## 10. Known Meta-Issues

- `AGENTS.md` at the repository root still references `v0.2.0-dev` and lists v0.3+
  features (EPUB, FTS5, multi-Work) as forbidden. The `CLAUDE.md` is already updated
  for v0.3.1-dev. `AGENTS.md` should be updated before Step 1 to avoid agent constraint
  confusion.
- `docs/ROADMAP.md` lists v0.4 features at a high level but may need refresh after
  the audit plan is finalized.
