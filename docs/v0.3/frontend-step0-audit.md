# Frontend v0.3 Step 0 — Audit & Implementation Plan

**Date:** 2026-05-29 | **Status:** DONE

---

## 1. Current Frontend State

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 + TypeScript 5 (strict mode) |
| Build | Vite 6 |
| Routing | React Router DOM 7 |
| Data Fetching | TanStack Query 5 |
| Styling | Plain CSS (no Tailwind/MUI/Ant Design — forbidden per CLAUDE.md) |
| Testing | Playwright 1.60 (27 e2e tests) |

### File Layout (45 source files)

```
src/
  main.tsx, router.tsx
  api/          — 7 files: client, health, topics, providers, documents, parse, chat
  pages/        — 6 pages: Dashboard, Topics, TopicDetail, TopicChat, Providers, NotFound
  layouts/      — AppLayout
  components/   — 6 shared: AnalysisOutputCard, EmptyState, ErrorBlock, HealthPanel,
                  LoadingBlock, StatusBadge, TokenRangeSlider
  features/
    analysis/   — 10 files: RunPanel, RunHistory, OutputsPanel, ModeSelector,
                  CostProjection, StageProgress, ChunkRangeSelector, ChunksMetaPanel,
                  LegacyAnalysisPanel, hooks
    provider/   — 2 files: EffectiveProviderConfigCard, ProviderConfigForm
    topic/      — 5 files: ChaptersPanel, DocumentPanel, ParsePanel,
                  ProviderBindingPanel, StoragePanel, TopicHeader
  utils/        — format
```

### API Client Coverage

| Backend API | Frontend client file | Status |
|-------------|---------------------|--------|
| `GET /api/health` | `api/health.ts` | Done |
| Provider CRUD | `api/providers.ts` | Done |
| Topic CRUD | `api/topics.ts` | Done |
| Document upload/get/delete | `api/documents.ts` | Done (`.txt` only) |
| Parse + chapters + chunks | `api/parse.ts` | Done |
| Analysis (v1 + v2) | `api/analysis.ts` | Done |
| Chat sessions + messages | `api/chat.ts` | Done |
| **`GET /documents/current/metadata`** | — | **Missing** |
| **`POST /search`** | — | **Missing** |
| **`POST /retrieve`** | — | **Missing** |
| **`GET /chunks/{id}/locator`** | — | **Missing** |
| **`GET /entities/{id}/evidence`** | — | **Missing** |
| **`GET /similar-scenes`** | — | **Missing** |

---

## 2. Gap Analysis

### 2.1 API Types (`api/types.ts`)

**Missing v0.3 types (10+ interfaces):**

- `DocumentMetadata` — `file_type`, `metadata` (parsed EPUB metadata or `{}` for TXT)
- `SearchRequest` / `SearchResult` / `SearchResponse` — query, methods, results with snippet/score/method
- `RetrieveRequest` / `CandidateResult` / `RetrieveResponse` — `source_type`, `source_id`, `chunk_id`, `matched_terms`, `source_locator`, `warning`
- `LocatorResponse` — `chunk_id`, `locator`, `excerpt`
- `EntityEvidenceResponse` — `atoms[]`, `chunks[]`, `outputs[]`
- `SimilarScenesResponse` — `results[]` with `chunk_id`, `snippet`, `score`, `locator`
- Existing types need updates: `Chapter` needs `source_href`, `nav_order`; `Chunk` needs `source_locator_json`; `ChatMessageRead.evidence_json` type is `string|null` but now returns structured objects

### 2.2 API Client Files

**New files needed:**
- `api/search.ts` — `POST /search`, `GET /metadata`, `GET /locator`
- `api/retrieve.ts` — `POST /retrieve`
- `api/entities.ts` — `GET /entities/{id}/evidence`, `GET /similar-scenes`

**Existing files to modify:**
- `api/documents.ts` — add `getDocumentMetadata()`
- `api/chat.ts` — no changes needed (same endpoints, new response shape)

### 2.3 Document Panel (`features/topic/DocumentPanel.tsx`)

**Current gaps:**
- File input `accept=".txt"` — must add `.epub`
- No file type indicator (TXT vs EPUB badge)
- No EPUB metadata display (title, creator, language, publisher, warnings)
- No EPUB chapter tree (spine-order chapters with `source_href`/`nav_order`)
- TXT workflow must continue working unchanged

### 2.4 Search Panel (new)

Backend exposes `POST /search` with FTS + keyword fallback. Frontend needs:
- Search input with submit on Enter
- Method filter checkboxes (fts, keyword_fallback)
- Result list with snippet, score, method badge
- Integration: where to place it? Options:
  - New tab/panel on TopicDetailPage (recommended — keeps context)
  - Separate sub-route `/topics/:topicId/search`

### 2.5 Search Result Cards (new)

Each search result needs:
- Snippet with highlighted CJK query terms where possible
- Method badge (`fts` / `keyword_fallback`)
- Score display (BM25 score, raw float)
- Chapter/chunk index reference
- Click to open locator (navigate to source chunk)

### 2.6 Chat Evidence v3 (upgrade)

Current `ChatBubble` renders evidence as:
```tsx
// Only handles string[] format
{typeof eq === "string" ? eq : JSON.stringify(eq)}
```

New backend returns structured objects:
```json
{ "text": "...", "source_type": "chunk", "source_id": "uuid", "chunk_id": "...", "method": "fts", "score": 0.85, "locator": {...} }
```

Changes needed:
- Detect if evidence item is `string` (old) or `object` (new)
- For objects: render `text`, show `source_type` badge, `method` + `score`, link to locator
- For strings: keep current rendering (backward compat)
- Show uncertainty warning differently when `no evidence` guard triggered

### 2.7 Retrieval Debug Drawer (new)

Backend exposes `POST /retrieve` with `persist_trace=true` returning `trace_id`. Frontend needs:
- "Debug" button on chat messages (or a debug tab)
- Call `/retrieve` with the same query
- Show ranked candidates with method/scores
- Compare with what the LLM actually used (evidence_json)
- Note: `/retrieve` results may differ from chat evidence because chat has legacy fallback

### 2.8 Entity Evidence Explorer (new)

Backend exposes `GET /entities/{id}/evidence`. Frontend needs:
- Entity search input (by name or stable_id)
- Results: atoms list, source chunks with excerpts + locators, related outputs
- Integration: could be a new panel on TopicDetailPage or a sub-page

### 2.9 Similar Scenes Panel (new)

Backend exposes `GET /similar-scenes?chunk_id=...&query=...`. Frontend needs:
- Two input modes: select a chunk from list, or type free-text query
- Results: chunk cards with snippet, score, locator
- Self-exclusion: when using chunk_id mode, seed chunk never appears
- Integration: pair with entity evidence or standalone panel

### 2.10 E2E Tests

27 Playwright tests exist for v0.2. v0.3 needs:
- EPUB upload UI flow
- Search panel interaction
- Chat evidence v3 rendering
- Entity evidence explorer
- Similar scenes panel

### 2.11 Frontend Constraints (CLAUDE.md)

**Forbidden:**
- Tailwind / MUI / Ant Design / Chakra / Redux / Zustand / MobX
- Graph visualization (v0.4)
- Cross-work analysis (v0.4)

**Must keep:**
- Plain CSS styling
- React 18 + TypeScript strict mode
- TanStack Query for data fetching
- React Router DOM for routing
- No new UI framework dependencies

---

## 3. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| TopicDetailPage already large (330 lines) — adding more panels could degrade maintainability | Medium | Use tabbed layout or collapsible sections; avoid monolithic growth |
| ChatBubble is a single large component (370+ lines) — evidence v3 changes touch deep rendering logic | Medium | Refactor evidence rendering into a separate `ChatEvidence` component first |
| EPUB chapter tree could be heavy for large EPUBs (100s of chapters) | Low | Virtualize or cap display; backend chapters endpoint already paginates |
| Structured evidence may break mobile/narrow displays | Low | Use responsive flex/grid; existing layout handles collapsible panels |
| `evidence_json` type change: `ChatMessageRead` has `string|null` but new data is objects parsed by `JSON.parse()` | Low | `ChatAnswerRead.evidence_json` is `unknown` — already handles both. `ChatMessageRead` returns raw string from list endpoint; frontend must `JSON.parse` before type-checking. |

---

## 4. Implementation Plan (12 Steps)

### Step 1 — API Types & Client
**Goal:** Add all v0.3 backend types and API client functions without changing any UI.

**Files:**
- `api/types.ts` — add v0.3 interfaces
- `api/documents.ts` — add `getDocumentMetadata()`
- `api/search.ts` (new) — `searchChunks()`, `getDocumentMetadata()`, `getChunkLocator()`
- `api/entities.ts` (new) — `getEntityEvidence()`, `getSimilarScenes()`

**Tests:** `tsc --noEmit` passes. Existing UI unchanged.

**Risk:** Low. Pure type/client additions, no UI impact.

---

### Step 2 — Document Panel: EPUB Upload + Metadata Card
**Goal:** Support EPUB upload and display parsed metadata.

**Files:**
- `features/topic/DocumentPanel.tsx` — update `accept` to `.txt,.epub`, add metadata card
- New component: `DocumentMetadataCard.tsx` — shows file_type badge, EPUB metadata fields (title, creator, language, publisher, warnings)

**Behavior:**
- Upload accepts `.txt` and `.epub`
- After upload + parse, metadata card appears below document info
- For TXT: `file_type: "txt"`, metadata = `{}`
- For EPUB: `file_type: "epub"`, metadata with source_format, title, creator, etc.
- Parse warnings displayed in a collapsible section

**Tests:** Typecheck + manual upload smoke.

---

### Step 3 — EPUB Chapter Tree
**Goal:** Show EPUB chapters in spine order with source_href.

**Files:**
- `features/topic/ChaptersPanel.tsx` — extend to show `source_href` and `nav_order` for EPUB
- New component: `EpubChapterTree.tsx` — tree view of EPUB chapters ordered by nav_order

**Behavior:**
- EPUB chapters display `source_href` (e.g., `Text/chapter001.xhtml`) and `nav_order`
- TXT chapters unchanged
- Chapter selection could link to locator view

**Tests:** Typecheck. EPUB smoke test.

---

### Step 4 — Topic Search Panel
**Goal:** Add search UI to TopicDetailPage.

**Files:**
- `features/search/TopicSearchPanel.tsx` (new) — search input, method toggles, result list
- `pages/TopicDetailPage.tsx` — add search panel section

**Behavior:**
- Search input with Enter-to-submit
- Method checkboxes: FTS, Keyword Fallback (both checked by default)
- Results: snippet, score, method badge, chapter/chunk index
- Empty state: "No results found"
- Error state: API error display
- Loading state: spinner while searching

**Tests:** Manual smoke. E2E in Step 10.

---

### Step 5 — Search Result Cards
**Goal:** Rich result cards with method/score/locator badges.

**Files:**
- `features/search/SearchResultCard.tsx` (new) — individual result card
- `features/search/SearchResultList.tsx` (new) — list container with score sorting

**Behavior:**
- Method badge: colored tag (`fts` = blue, `keyword_fallback` = green)
- Score display: "Score: 2.35" or normalized to stars/bars
- Snippet: truncated with ellipsis
- Locator: clickable chapter/chunk reference (could open chunk locator detail or scroll to chunk)
- Click on result → open chunk locator modal/inline

**Tests:** Typecheck. Visual review with real search results.

---

### Step 6 — Chat Evidence v3
**Goal:** Render structured evidence objects in chat bubbles. Backward-compatible with old string[] format.

**Files:**
- `pages/TopicChatPage.tsx` — refactor ChatBubble evidence section
- New component: `features/chat/ChatEvidenceList.tsx` — renders evidence items

**Behavior:**
- Detect evidence format: `string[]` (old) vs `object[]` (new)
- Object items show: snippet text, source_type badge (chunk/atom/output), method + score, clickable locator
- String items: keep existing rendering
- Uncertainty: styled warning box; special styling when `no evidence` guard triggered
- Collapsible evidence list with item count badge

**Backward compat:** Old messages with `evidence_json: ["string"]` must not crash and must render correctly.

**Tests:** Manual with both old and new-format messages. E2E in Step 10.

---

### Step 7 — Retrieval Debug Drawer
**Goal:** Show retrieval trace for debugging chat evidence.

**Files:**
- `features/chat/RetrievalDebugDrawer.tsx` (new) — slide-out drawer showing trace
- `pages/TopicChatPage.tsx` — add "Debug" button to chat messages

**Behavior:**
- "Debug" button on each assistant message (or a debug tab in right panel)
- Calls `POST /retrieve` with the same query
- Shows: ranked candidates with method, score, matched_terms, locator
- Side-by-side comparison with what the LLM actually used (evidence_json)
- Shows `warning` if semantic_rerank requested but disabled

**Tests:** Manual with real queries. E2E in Step 10.

---

### Step 8 — Entity Evidence Explorer
**Goal:** Browse entities and their evidence.

**Files:**
- `features/evidence/EntityEvidencePanel.tsx` (new) — entity search + evidence display
- `features/evidence/EvidenceSourceBadge.tsx` (new) — source type/method badge
- `pages/TopicDetailPage.tsx` — add entity evidence section

**Behavior:**
- Entity search: type a name or stable_id
- Results: atoms list, source chunks with locators, related outputs
- Each chunk: excerpt + chapter/chunk index + clickable locator
- Each output: title + excerpt + output_type badge
- Requires analysis to have been run (atoms come from analysis pipeline)
- Empty state: "No atoms found. Run analysis first."

**Tests:** Manual with analyzed topic. E2E in Step 10.

---

### Step 9 — Similar Scenes Panel
**Goal:** Find scenes similar to a selected chunk or query.

**Files:**
- `features/evidence/SimilarScenesPanel.tsx` (new) — two-mode input + results
- `pages/TopicDetailPage.tsx` — add similar scenes section

**Behavior:**
- Mode 1 (chunk_id): dropdown or click-to-select a chunk from the chunk list
- Mode 2 (query): free-text input
- Results: chunk cards with snippet, score, locator
- Self-exclusion: selected seed chunk never appears
- Empty state: "Select a chunk or enter a query"

**Tests:** Manual. E2E in Step 10.

---

### Step 10 — E2E Tests Expansion
**Goal:** Playwright tests for new v0.3 features.

**Files:**
- `e2e/search.spec.ts` (new)
- `e2e/evidence.spec.ts` (new)
- `e2e/chat-evidence.spec.ts` (new)
- `e2e/epub-upload.spec.ts` (new)

**Coverage:**
- EPUB upload + metadata display
- Search: CJK query → results appear with method badges
- Chat: structured evidence renders, uncertainty shows on empty retrieval
- Entity evidence: atom lookup returns chunks
- Similar scenes: chunk_id mode excludes self

**Tests:** `npx playwright test` passes.

---

### Step 11 — Frontend Smoke Test / Documentation Pass
**Goal:** Update frontend docs and manual smoke test.

**Files:**
- `docs/FRONTEND_SMOKE_TEST.md` — add v0.3 steps
- `docs/FRONTEND_API_CONTRACT.md` — already updated in backend Steps 6-10 (verify completeness)

**Smoke test additions:**
- EPUB upload + parse + metadata + chapter tree
- Search: CJK query → results
- Similar scenes: by query and by chunk_id
- Entity evidence: atom lookup
- Chat: structured evidence rendering, old evidence backward compat

---

### Step 12 — Final Review & Release Prep
**Goal:** Polish, final typecheck/lint/build pass, tag prep.

**Files:**
- All touched files — final review pass
- `frontend/package.json` — bump version to `0.3.0-dev`
- `CLAUDE.md` — update frontend v0.3 status

**Checks:**
- `npm run typecheck` clean
- `npm run lint` clean
- `npm run build` clean
- All e2e tests pass
- No forbidden tech introduced
- Backward compat: TXT workflows, v1/v2 analysis, old chat messages all work

---

## 5. Dependency Order

```
Step 1 (API types + client)           ← MUST be first (all other steps depend on it)
  ↓
Step 2 (EPUB Upload + Metadata)       ← can parallel with Step 3
Step 3 (EPUB Chapter Tree)            ← can parallel with Step 2
  ↓
Step 4 (Search Panel)                 ← can parallel with Step 6
Step 5 (Search Result Cards)          ← depends on Step 4
  ↓
Step 6 (Chat Evidence v3)             ← can parallel with Steps 7-9
Step 7 (Retrieval Debug Drawer)       ← depends on Step 6
  ↓
Step 8 (Entity Evidence Explorer)     ← independent
Step 9 (Similar Scenes Panel)         ← independent
  ↓
Step 10 (E2E Tests)                   ← depends on Steps 2-9
  ↓
Step 11 (Smoke Test / Docs)           ← depends on Step 10
  ↓
Step 12 (Final Review)                ← depends on Step 11
```

**Parallelizable groups:**
- Group A: Steps 2 + 3 (Document panel features)
- Group B: Steps 4 + 6 (Search + Chat — independent panels)
- Group C: Steps 8 + 9 (Evidence + Similar Scenes — share `api/entities.ts`)

## 6. Estimated Effort

| Step | Files | Complexity | Est. Time |
|------|-------|-----------|-----------|
| 1 | 3-4 new/modified | Low | 30 min |
| 2 | 2 modified, 1 new | Low | 45 min |
| 3 | 1 modified, 1 new | Low | 30 min |
| 4 | 1 new, 1 modified | Medium | 1 hr |
| 5 | 2 new | Low | 45 min |
| 6 | 1 modified, 1 new | Medium | 1.5 hr |
| 7 | 1 new, 1 modified | Medium | 1 hr |
| 8 | 2 new, 1 modified | Medium | 1 hr |
| 9 | 1 new, 1 modified | Medium | 45 min |
| 10 | 4 new | Medium | 1.5 hr |
| 11 | 2 modified | Low | 30 min |
| 12 | 2-3 modified | Low | 30 min |
| **Total** | **~25 files** | | **~10 hrs** |
