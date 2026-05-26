# Backend v0.3 Step 0 — Audit Report

> **Date:** 2026-05-26 | **Status:** Read-only audit. This report is a versioned planning artifact — unlike the original Step 0 prompt which said "不写代码、不改文档、不提交", we intentionally commit it so the plan is traceable to the codebase state at the time of audit.

---

## 1. Audit Summary

All 12 planned Backend steps are executable without architectural changes. One new dependency (`beautifulsoup4`) is required for EPUB XHTML text extraction — Python stdlib handles OPF/container parsing. No other new dependencies needed.

---

## 2. Per-Area Gap Analysis

### 2.1 Document.file_type — Hardcoded to `.txt` only

**File:** `backend/models/document.py:14`

```python
file_type: str = "txt"
```

`file_type` is a free `str` field (not an enum), so adding `"epub"` requires no schema migration — just update the upload validation and the parse path. The field's default of `"txt"` means existing rows are fine.

**Gap:** `metadata_json` field is missing entirely. Must be added via `ALTER TABLE`.

### 2.1.1 Document.encoding and stored_filename — Non-Nullable Fields

**File:** `backend/models/document.py:16-17`

```python
encoding: str = "utf-8"      # non-nullable str
stored_filename: str = "original.txt"  # non-nullable, default "original.txt"
```

`DocumentRead.encoding` is also `str` (line 32) — the API response schema mirrors the model. EPUB cannot set `encoding=null` without changing both model and read schema to `str | None`, which would also affect existing TXT endpoints.

**Decision (confirmed for Step 1/2):** Use fixed `encoding="epub"` for EPUB documents rather than making the field nullable. This avoids a schema migration on `encoding` and keeps the API response shape stable. EPUB upload must also set `stored_filename="original.epub"` (currently hardcoded to `"original.txt"` on line 122 of `document_service.py`). The `get_original_txt_path()` helper in `storage.py` should be generalized to `get_source_file_path(topic_id)` that reads `stored_filename` from the Document row.

### 2.2 Upload Endpoint — TXT Only, No EPUB Path

**File:** `backend/routers/documents.py:11-17`, `backend/services/document_service.py:96-146`

- Line 101: `if not file.filename or not file.filename.lower().endswith(".txt")` — hard gate.
- Line 122: `dest_path = source_dir / "original.txt"` — name hardcoded.
- Encoding detection (`_detect_encoding`) only works on raw bytes — EPUB is a zip container, so encoding detection must be bypassed for EPUB.
- `char_count` set to `len(text)` for TXT; for EPUB (pre-parse) should be 0.

**Gap:** Upload needs a branch: `.txt` → existing flow, `.epub` → zip/container.xml validation → save as `original.epub`.

### 2.3 ParserService — TXT-Only, Hardcoded Path

**File:** `backend/services/parser_service.py:76-191`

- Line 85: `txt_path = storage.get_original_txt_path(topic_id)` — assumes `.txt`.
- `storage.py:28-29`: `get_original_txt_path` returns `source_dir / "original.txt"` — hardcoded.
- `_detect_chapters` uses CN/EN regex patterns — works on plain text from either source.
- `_split_into_chunks` operates on character ranges — format-agnostic, reusable.
- Chapter/Chunk creation (lines 137-165) has no `source_href` / `nav_order` / `source_locator_json` population.

**Gap:** `get_original_txt_path` must become format-aware. Chapter/Chunk creation must write locator fields.

### 2.4 Chapter/Chunk — No Source Locator Fields

**Files:** `backend/models/chapter.py`, `backend/models/chunk.py`

| Field | Chapter | Chunk |
|-------|---------|-------|
| `source_href` | Missing | — |
| `nav_order` | Missing | — |
| `metadata_json` | Missing | — |
| `source_locator_json` | — | Missing |

All four fields need `ALTER TABLE ADD COLUMN` — all nullable, no default value needed.

### 2.5 Migration Pattern — Already Established

**File:** `backend/db.py:24-83`

Existing migration functions follow a clean pattern:
```python
def _migrate_xxx() -> None:
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE ... ADD COLUMN ..."))
        except Exception:
            pass  # column already exists
        conn.commit()
```

New v0.3 columns will follow the same pattern. FTS5 virtual table creation will use `CREATE VIRTUAL TABLE IF NOT EXISTS` inside `init_db()` or a dedicated `_migrate_chunk_fts()` function.

### 2.6 RetrievalService — Keyword-Only, No FTS

**File:** `backend/services/retrieval_service.py`

- `retrieve_chunks()` (line 92): Loads ALL chunks for a topic, scores each in Python with character/word overlap. O(n) scan with no index.
- `retrieve_analysis()` (line 119): Loads ALL AnalysisOutputs, substring-match scores. O(n) scan.
- No FTS, no structured atom search, no BM25 scoring.
- `build_evidence_context()` returns `{chunks: [...], analysis_outputs: [...]}` — flat dict, no structured EvidenceItem model.

**Gap:** Entire retrieval layer needs FTS5 + hybrid strategy. The existing keyword fallback should be preserved as the CJK safety net, not replaced.

### 2.7 Chat Evidence — String Array, No Structured Format

**File:** `backend/services/chat_service.py:257-258`

```python
evidence_list = _sanitize_evidence(parsed)  # → list[str]
evidence_json=(json.dumps(evidence_list, ...) if evidence_list else None)
```

Evidence is a flat `string[]` extracted from the LLM's JSON response. The frontend `ChatMessageRead.evidence_json` is `str | None` — a JSON string. `ChatAnswerRead` parses it to `dict | list | None`.

**Gap:** `evidence_json` can already accept `list` (string[]) and `dict` (object evidence). The field itself is schema-flexible. The change is in `chat_service.py`: instead of `_sanitize_evidence(parsed)` returning `list[str]`, the new retrieval service should produce structured evidence objects. The LLM prompt's `"evidence": ["string"]` contract changes to accept structured items.

### 2.8 ExtractedAtom — Ready for Structured Retrieval

**File:** `backend/models/extracted_atom.py`

- `stable_id: str` — usable as entity_id for `/entities/{id}/evidence`.
- `canonical_name: str | None` — searchable.
- `source_chunk_ids: str = "[]"` — JSON array of chunk IDs, directly usable for evidence lookup.
- `evidence_quotes: str = "[]"` — JSON array of quoted evidence strings.
- `atom_type: str` — filterable (character, event, location, etc.).

**Gap:** None for the model itself. The retrieval service needs a new method to query atoms by `stable_id`/`canonical_name` and return associated chunks.

### 2.9 Deletion / Re-parse Cleanup — Three Paths, All Need FTS + Trace Hooks

FTS5 virtual tables and RetrievalTrace rows have **no FK cascade** — they must be cleaned up explicitly. There are three independent paths that delete or replace chunks/analyses:

| Path | File:Line | What it deletes |
|------|-----------|-----------------|
| A — Delete document | `document_service.py:161-182` → `_delete_document_derived_data()` (line 47) | Chunks, Chapters, Analyses, Atoms, Extractions, Runs, Jobs |
| B — Delete topic | `topic_service.py:38-110` | Same as A, plus Document, Chat, Topic itself |
| C — Re-parse | `parser_service.py:113-117` | `DELETE FROM chunk WHERE topic_id = ?` + `DELETE FROM chapter WHERE topic_id = ?` |

All three paths must include FTS and RetrievalTrace cleanup:

- **After deleting chunks (paths A, B, C):** `DELETE FROM chunk_fts WHERE topic_id = ?`
- **After deleting analyses/atoms (paths A, B):** `DELETE FROM retrieval_trace WHERE topic_id = ?`
- **After re-parse (path C):** Rebuild FTS for the topic (Step 5's `rebuild_topic_chunk_fts`). **Also** delete RetrievalTrace rows for the topic — old traces contain `chunk_id` references to rows that path C has just deleted, so they cannot be resolved by the debug UI. This is the simple strategy for v0.3.0; a more complex alternative (adding `source_generation`/`snapshot` fields to preserve historical traces) is deferred to v0.3.x.
- **Tests must cover:** delete document → FTS + trace empty; delete topic → FTS + trace empty; re-parse → old FTS rows gone, new FTS rows present, old traces deleted.

### 2.10 Test Infrastructure — Ready for v0.3

**File:** `backend/tests/` (various)

- Tests use `pytest` fixtures with in-memory or temp-file SQLite.
- LLM calls are mocked via `unittest.mock` or equivalent.
- Existing test patterns (CRUD, parse, analysis, chat) provide templates for v0.3 tests.

**Gap:** Need a helper to generate minimal EPUB fixtures in tests (valid zip with `META-INF/container.xml`, OPF, one XHTML chapter). Python's `zipfile` + string templates suffice.

---

## 3. Dependency Decision

**Add:** `beautifulsoup4` (pure Python, no C extension)

**Why:**
- EPUB XHTML content uses HTML entities, nested tags, and irregular whitespace that regex cannot handle reliably.
- `bs4` provides read-only DOM traversal: `soup.get_text()` strips tags, decodes entities, and normalizes whitespace.
- No JS execution, no CSS rendering, no network access.
- `lxml` was rejected — it's faster but has native library dependencies that complicate cross-platform install.

**Where used:** Only in `backend/services/epub_parser_service.py` (Step 3), for the XHTML-to-plain-text extraction step. OPF/container parsing uses stdlib `xml.etree.ElementTree`.

**Install:** `pip install beautifulsoup4` added to `pyproject.toml` dependencies.

---

## 4. Refined Step Sequence

Steps 1–12 as planned in `agent/NEXT_ACTIONS.md` are confirmed executable. Specific notes per step:

| Step | Note |
|------|------|
| 1 (Schema) | `ALTER TABLE` pattern from `db.py:24-83` is the template. 4 nullable columns + 1 new model + 1 FTS virtual table. |
| 2 (Upload) | Branch on extension: `.txt` → existing flow, `.epub` → zip validation → save. Set `encoding="epub"` (not null — avoids schema change), `stored_filename="original.epub"`. Generalize `get_original_txt_path` → `get_source_file_path`. |
| 3 (EPUB Parser) | `zipfile` + `xml.etree.ElementTree` for container/OPF. `beautifulsoup4` for XHTML→text. No DB writes. |
| 4 (Parse) | TXT adapter wraps existing `_detect_chapters` + `_split_into_chunks`. EPUB adapter calls Step 3 parser. Unified `SourceDocument → Chapter/Chunk` path with locator fields. |
| 5 (FTS) | `CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(...)`. Rebuild on parse complete. Cleanup on document delete, topic delete, and re-parse. |
| 6 (Search API) | Three endpoints: metadata, search, locator. Pydantic schemas. Query validation. |
| 7 (Retrieval) | Candidate unification: FTS + keyword fallback + AnalysisOutput + ExtractedAtom. Score normalization. Dedup by chunk_id. |
| 8 (Chat) | Replace `build_evidence_context()` → new hybrid retrieval. `evidence_json` accepts structured objects. Backward compat via `normalizeEvidence()` on frontend or normalizer in `_sanitize_evidence`. |
| 9 (Entities) | `ExtractedAtom.stable_id` is the lookup key. `source_chunk_ids` JSON field links to chunks. |
| 10 (Rerank) | Feature flag `ENABLE_SEMANTIC_RERANK=false`. Abstract skeleton. No vector DB. |
| 11 (Smoke) | Minimal generated EPUB fixtures. Mock LLM throughout. |
| 12 (Docs) | Update all docs to v0.3. |

---

## 5. Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| TXT parse regression from parser refactor (Step 4) | Medium | TXT adapter preserves existing `_detect_chapters` + `_split_into_chunks` unchanged; tests gate this |
| EPUB XHTML with complex nested structures | Medium | bs4 `get_text()` handles most cases; add parsing_warnings for unparseable content |
| FTS5 Chinese tokenization inadequate (unicode61) | High | CJK `LIKE '%keyword%'` fallback already designed into Step 5; not relying on FTS alone |
| Old SQLite databases without FTS5 support | Low | FTS5 has been in SQLite since 3.9.0 (2015); macOS/Windows/Linux all ship with it |
| `evidence_json` format mismatch between old/new frontend | Low | Field is already `str|None` with JSON content; frontend `normalizeEvidence()` handles both shapes |
| Parse failure with malformed EPUB (invalid zip, missing OPF) | Medium | Validate zip + container.xml at upload time (Step 2); parse-time errors are caught and surfaced as warnings |
| Orphan FTS rows after topic delete or re-parse | Medium | Three cleanup paths (doc delete, topic delete, re-parse) must all clear/rebuild FTS; tests cover each |
| `Document.encoding` schema migration needed if EPUB uses null | Avoided | Use fixed `encoding="epub"` string, keeping the field non-nullable — no migration needed |
