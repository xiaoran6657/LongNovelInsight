# Frontend v0.4 Step 0 — Audit & Implementation Plan

> Generated 2026-06-04 from current `main` (post backend v0.4 Steps 1-10).

## 1. Current Frontend Architecture

### 1.1 Route map

| Path | Page | State |
|------|------|-------|
| `/` | `DashboardPage` | Stable |
| `/providers` | `ProvidersPage` | Stable |
| `/topics` | `TopicsPage` | Stable |
| `/topics/:topicId` | `TopicDetailPage` | **Heavily modified in v0.4** |
| `/topics/:topicId/chat` | `TopicChatPage` | Lightly modified |
| `*` | `NotFoundPage` | Stable |

### 1.2 API module inventory

| File | Purpose | v0.4 changes |
|------|---------|-------------|
| `client.ts` | `apiRequest<T>()` wrapper | None |
| `types.ts` | Shared TypeScript types | **Add Work, Entity, Graph, Timeline types** |
| `health.ts` | `GET /api/health` | None |
| `providers.ts` | Provider CRUD | None |
| `topics.ts` | Topic CRUD + config | None |
| `documents.ts` | Document upload/delete | **Add work-scoped variants** |
| `parse.ts` | Parse/chapters/chunks | **Add work-scoped variants** |
| `analysis.ts` | Analysis runs/outputs | **Add work-id parameter** |
| `chat.ts` | Chat sessions/messages | **Add work_ids to send-message** |
| `search.ts` | `POST /search` | **Add work_ids filter** |
| `retrieve.ts` | `POST /retrieve` | **Add work_ids filter** |
| `entities.ts` | Entity evidence | **Add global entity list/detail/mentions** |
| _(new)_ `works.ts` | Work CRUD | **New module** |
| _(new)_ `crossWork.ts` | Cross-work runs | **New module** |
| _(new)_ `graphs.ts` | Character graph | **New module** |
| _(new)_ `timeline.ts` | Timeline | **New module** |

### 1.3 Feature directory inventory

| Directory | Components | v0.4 changes |
|-----------|-----------|-------------|
| `analysis/` | 12 files (run panel, history, mode selector, cost projection, etc.) | Add work-id to run creation; work-scoped outputs panel |
| `chat/` | `ChatEvidenceList.tsx` | Add work metadata display |
| `document/` | `DocumentMetadataCard.tsx` | Add work-id label |
| `evidence/` | `EntityEvidencePanel`, `SimilarScenesPanel` | **Replace with global entity registry** |
| `provider/` | `EffectiveProviderConfigCard`, `ProviderConfigForm` | Stable |
| `search/` | 5 files (search panel, results, debug drawer, badges) | Add work-id filter checkboxes |
| `topic/` | 8 files (header, panels, tree) | Add Work selector; **restructure** |
| _(new)_ `works/` | Work list, cards, forms, upload panel | **New feature** |
| _(new)_ `crossWork/` | Dashboard, run panel, status cards | **New feature** |
| _(new)_ `entities/` | Entity registry table, detail drawer | **New feature** |
| _(new)_ `graphs/` | Cytoscape graph component, filters, evidence panel | **New feature** |
| _(new)_ `timeline/` | Timeline list/rail, filters, source links | **New feature** |

### 1.4 TopicDetailPage structure

`TopicDetailPage` is the largest page (~300+ lines) and will be the most modified. Current sections:

1. Topic header + provider binding
2. Document upload/delete panel
3. Parse panel
4. Chapters panel + EPUB tree
5. Search panel
6. Chunks meta + range selector
7. Analysis mode + run creation
8. Active run panel
9. Run history
10. Outputs panel
11. Entity evidence panel
12. Similar scenes panel

v0.4 must add: Work selector (top-level), cross-work dashboard, entity registry, graph, timeline — without making the page unmanageably long. Recommended: **tab navigation** or collapsible sections.

### 1.5 React Query patterns

All server state uses TanStack Query v5:
- `useQuery` for reads, `useMutation` for writes
- Query keys follow `["resource", topicId, ...sub]` pattern
- Cache invalidation via `queryClient.invalidateQueries`
- `useInfiniteQuery` for paginated run history

New v0.4 features must follow the same pattern.

### 1.6 Playwright E2E tests

| File | Tests | v0.4 impact |
|------|-------|------------|
| `basic.spec.ts` | Health, dashboard, providers | None |
| `analysis-v2.spec.ts` | 19 tests (analysis pipeline) | **Add work-scoped analysis tests** |
| `topic-detail.spec.ts` | 2 tests | **Add Work management tests** |
| `v0.3-features.spec.ts` | 11 tests (EPUB, search, evidence) | **Add v0.4 feature tests** |
| _(new)_ `v0.4-features.spec.ts` | Work, entities, graph, timeline | **New file** |

---

## 2. Files to Create

### 2.1 New API modules

| File | Endpoints |
|------|-----------|
| `src/api/works.ts` | `listWorks`, `createWork`, `getWork`, `updateWork`, `deleteWork`, `uploadToWork`, `getWorkDocument`, `parseWork`, `getWorkChapters`, `getWorkChunks`, `createWorkAnalysisRun`, `listWorkAnalysisRuns`, `listWorkAnalysisOutputs` |
| `src/api/crossWork.ts` | `createCrossWorkRun`, `listCrossWorkRuns`, `getCrossWorkRun`, `listEntities`, `getEntity`, `listEntityMentions`, `buildEntityRegistry` |
| `src/api/graphs.ts` | `getCharacterGraph`, `buildGraph` |
| `src/api/timeline.ts` | `getTimeline`, `buildTimeline` |

### 2.2 New feature directories and components

| Directory | Files | Purpose |
|-----------|-------|---------|
| `features/works/` | `WorkList.tsx`, `WorkCard.tsx`, `WorkCreateForm.tsx`, `WorkDetail.tsx`, `WorkUploadPanel.tsx`, `WorkAnalysisPanel.tsx` | Work CRUD + upload + analysis entry |
| `features/crossWork/` | `CrossWorkDashboard.tsx`, `CrossWorkRunPanel.tsx` | Dashboard + run status |
| `features/entities/` | `EntityRegistryTable.tsx`, `EntityDetailDrawer.tsx` | Global entity browser |
| `features/graphs/` | `CharacterGraph.tsx`, `GraphFilters.tsx`, `GraphEvidencePanel.tsx` | Cytoscape graph UI |
| `features/timeline/` | `TimelineView.tsx`, `TimelineItem.tsx`, `TimelineFilters.tsx` | Timeline list + filters |

### 2.3 Modified files

| File | Changes |
|------|---------|
| `src/api/types.ts` | Add Work/CWE/Graph/Timeline types |
| `src/api/chat.ts` | Add `work_ids` to `sendMessage` |
| `src/api/documents.ts` | Add work-scoped upload/get/delete variants |
| `src/api/parse.ts` | Add work-scoped parse/chapters/chunks variants |
| `src/api/analysis.ts` | Add `work_id` parameter to run creation |
| `src/api/search.ts` | Add `work_ids` filter to search request |
| `src/api/retrieve.ts` | Add `work_ids` filter to retrieve request |
| `src/pages/TopicDetailPage.tsx` | **Major**: add tab navigation, Work selector, cross-work sections |
| `src/pages/TopicChatPage.tsx` | Add `work_ids` to chat message send |
| `src/router.tsx` | No new routes needed (Work UI lives inside Topic detail) |

---

## 3. Key Design Decisions

### 3.1 Tab navigation in TopicDetailPage

**Decision:** Add a horizontal tab bar at the top of TopicDetailPage with tabs: Overview (current content), Works, Entities, Graph, Timeline.

**Rationale:** The page is already too long. Tabs keep existing UX intact while adding discoverability for new features. The "Overview" tab preserves the existing single-page layout, minimizing disruption.

### 3.2 Work selector component

**Decision:** A `<WorkSelector>` component renders at the top of the Overview tab (and above content in other tabs). It lists all Works for the current Topic, highlights the active one, and provides "Create Work" action.

**State:** `activeWorkId` stored in component state (not URL). SessionStorage persistence similar to `useActiveRunPersistence`.

### 3.3 Cytoscape.js for character graph

**Decision:** Use `cytoscape` directly (not `react-cytoscapejs`) wrapped in a single `<CharacterGraph>` component. This avoids an extra dependency and gives full control over initialization/cleanup.

**Bundle impact:** cytoscape ~200KB minified. Acceptable for v0.4.

**Causal graph:** Deferred to v0.4.1 unless backend causal graph endpoint is built.

### 3.4 No new route for Work detail

**Decision:** Work management lives inside TopicDetailPage tabs. No new URL routes like `/works/:workId`. This keeps routing simple and matches the single-Topic context.

### 3.5 Entity registry replaces EntityEvidencePanel

**Decision:** The new `EntityRegistryTable` + `EntityDetailDrawer` replaces the old `EntityEvidencePanel` for v0.3 entity evidence. The old panel is kept but moved behind a "Legacy" toggle or tab.

### 3.6 Mock Playwright tests for all new features

**Decision:** All v0.4 E2E tests use mocked API responses (same pattern as existing `v0.3-features.spec.ts`). No real LLM calls. New `v0.4-features.spec.ts` file.

---

## 4. Compatibility Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| TopicDetailPage grows beyond maintainable size | Medium | Tab navigation; extract sub-panels to separate components |
| Existing v0.3 Playwright tests break | Medium | Keep old DOM structure in Overview tab; update selectors where needed |
| Cytoscape.js bundle size | Low | Code-split the Graph tab; lazy-load cytoscape |
| TypeScript strict errors from new types | Low | Incremental type additions; run `tsc --noEmit` after each step |
| Search/chat work_ids not wired in UI | Low | Add optional filter checkboxes; default empty = no filter (backward compat) |
| CSS conflicts with existing layout | Low | Use existing CSS patterns; minimal new styles |

---

## 5. Proposed Step Order

| Step | Description | New files | Modified files |
|------|-------------|-----------|---------------|
| **1** | API types + client modules | `works.ts`, `crossWork.ts`, `graphs.ts`, `timeline.ts` | `types.ts`, `documents.ts`, `parse.ts`, `analysis.ts`, `search.ts`, `retrieve.ts`, `chat.ts` |
| **2** | Work list + create form + selector | `WorkList.tsx`, `WorkCard.tsx`, `WorkCreateForm.tsx` | `TopicDetailPage.tsx` |
| **3** | Work upload + parse + analysis | `WorkUploadPanel.tsx`, `WorkAnalysisPanel.tsx` | `TopicDetailPage.tsx`, `analysisSelection.ts` |
| **4** | Cross-work dashboard + run panel | `CrossWorkDashboard.tsx`, `CrossWorkRunPanel.tsx` | `TopicDetailPage.tsx` |
| **5** | Entity registry table + drawer | `EntityRegistryTable.tsx`, `EntityDetailDrawer.tsx` | `TopicDetailPage.tsx` |
| **6** | Character graph + filters | `CharacterGraph.tsx`, `GraphFilters.tsx`, `GraphEvidencePanel.tsx` | `TopicDetailPage.tsx` |
| **7** | Timeline view + filters | `TimelineView.tsx`, `TimelineItem.tsx`, `TimelineFilters.tsx` | `TopicDetailPage.tsx` |
| **8** | E2E tests + docs | `v0.4-features.spec.ts` | `README.md`, `FRONTEND_SMOKE_TEST.md` |

Steps 1-3 are sequential (types → Work UI → upload/analysis).
Steps 4-7 can be parallelized after Step 3.
Step 8 runs throughout.

---

## 6. Test Strategy

### 6.1 Playwright E2E tests (`v0.4-features.spec.ts`)

Minimum coverage:

1. Work list empty state + create Work form
2. Work list shows created Works ordered by series_index
3. Upload TXT/EPUB to Work via Work panel
4. Parse Work and view chapters/chunks
5. Cross-work dashboard shows stats after build
6. Entity registry table with filters and detail drawer
7. Character graph renders nodes/edges (mocked)
8. Timeline renders ordered items with filters (mocked)
9. Work selector switches active Work
10. Existing search/analysis tabs still work

### 6.2 Existing test compatibility

- `analysis-v2.spec.ts` — should pass with work_id=None (default behavior unchanged)
- `v0.3-features.spec.ts` — should pass; old panels accessible via Overview tab
- `basic.spec.ts`, `topic-detail.spec.ts` — no expected breakage

---

## 7. Acceptance Criteria (this step)

- [x] This document exists at `docs/v0.4/frontend-step0-audit.md`.
- [x] Current routes, API modules, feature directories documented.
- [x] Exact new files to create listed with module/component names.
- [x] Exact existing files to modify listed with specific changes.
- [x] Design decisions documented (tabs, Cytoscape, no new routes).
- [x] Compatibility risks identified with mitigations.
- [x] Step order defined with dependencies.
- [x] Test strategy covers new features + backward compatibility.
- [x] Frontend typecheck/build lint baseline passes.
