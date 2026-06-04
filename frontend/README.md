# LongNovelInsight Frontend

React + TypeScript + Vite frontend for local-first LLM-powered long-novel analysis.

## Quick Start

```bash
cd frontend
npm install
npm run dev           # → http://localhost:5173
npm run typecheck     # TypeScript check
npm run lint          # ESLint
npm run build         # Production build → dist/
npm run check         # All three checks at once
npm run e2e           # Playwright end-to-end tests (44 tests: 38 v0.3 + 6 v0.4)
```

The backend must be running separately:

```bash
cd backend
conda activate LongNovelInsight
uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/health
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend API base URL |

Copy `.env.example` to `.env.local` and customize.

## Project Structure

```
frontend/
├── index.html
├── package.json              # React 18, Vite 6, TypeScript 5
├── vite.config.ts            # @vitejs/plugin-react, port 5173
├── playwright.config.ts      # Playwright e2e config (44 tests)
├── tsconfig.json             # strict mode, ES2020, jsx react-jsx
├── eslint.config.js          # typescript-eslint + recommended
├── .env.example              # VITE_API_BASE_URL template
├── e2e/                      # Playwright end-to-end tests
│   ├── basic.spec.ts         # Basic smoke tests
│   ├── analysis-v2.spec.ts   # v0.2 analysis pipeline tests
│   ├── v0.3-features.spec.ts # v0.3 EPUB/search/evidence tests (11 tests)
│   └── v0.4-features.spec.ts # v0.4 Work CRUD + form body tests (6 tests)
└── src/
    ├── vite-env.d.ts         # ImportMetaEnv type definitions
    ├── main.tsx              # React root render (QueryClient + Router)
    ├── router.tsx            # React Router route definitions
    ├── api/                  # API client and endpoint modules
    │   ├── client.ts         # apiRequest<T>() with fetch
    │   ├── types.ts          # Shared TypeScript types (AnalysisRun with usage breakdown)
    │   ├── health.ts         # GET /api/health
    │   ├── providers.ts      # Provider CRUD + test + presets
    │   ├── topics.ts         # Topic CRUD + provider config + effective config + recommendation
    │   ├── documents.ts      # Document upload / delete / metadata
    │   ├── parse.ts          # Parse / chapters / chunks / storage
    │   ├── analysis.ts       # Analysis run / outputs / jobs / status
    │   ├── chat.ts           # Chat sessions / messages / delete message
    │   ├── search.ts         # v0.3: POST /search
    │   ├── retrieve.ts       # v0.3: POST /retrieve
    │   ├── entities.ts       # v0.3: GET entity evidence + similar scenes
    │   ├── works.ts          # v0.4: Work CRUD + upload/parse/analysis
    │   ├── crossWork.ts      # v0.4: cross-work runs + entity registry
    │   ├── graphs.ts         # v0.4: character graph
    │   └── timeline.ts       # v0.4: timeline
    ├── features/             # Feature-based UI components + hooks
    │   ├── analysis/         # v0.2+ analysis run UI: mode selector, run panel, history, outputs
    │   │   ├── AnalysisRunPanel.tsx       # Active run detail with token breakdown
    │   │   ├── AnalysisRunHistory.tsx     # Past runs list (paginated)
    │   │   ├── AnalysisOutputsPanel.tsx   # Unified v1/v2 output view
    │   │   ├── AnalysisModeSelector.tsx   # Mode: preview/range/full/incremental
    │   │   ├── AnalysisCostProjection.tsx  # Cost estimate with retry buffer note
    │   │   ├── AnalysisStageProgress.tsx  # Extraction/Merge/Final progress bars
    │   │   ├── ChunksMetaPanel.tsx        # Chunk statistics
    │   │   ├── ChunkRangeSelector.tsx     # Chunk/chapter range input
    │   │   ├── LegacyAnalysisPanel.tsx    # v0.1 legacy analysis UI
    │   │   ├── analysisSelection.ts       # estimateTokens (aligned with backend formula)
    │   │   ├── useAnalysisRun.ts          # Run query + polling hook
    │   │   └── useActiveRunPersistence.ts # SessionStorage run ID persistence
    │   ├── search/           # v0.3: search panel and results
    │   │   ├── TopicSearchPanel.tsx       # Query input + method filter + debug drawer
    │   │   ├── SearchResultList.tsx       # Result count + card list
    │   │   ├── SearchResultCard.tsx       # Snippet, method badge, score, locator
    │   │   ├── RetrievalMethodBadge.tsx   # Colored badge for each retrieval method
    │   │   └── RetrievalDebugDrawer.tsx   # Inline collapsible trace viewer
    │   ├── evidence/         # v0.3: entity evidence and similar scenes
    │   │   ├── EntityEvidencePanel.tsx    # Atoms/chunks/outputs for an entity
    │   │   └── SimilarScenesPanel.tsx     # By-query or by-chunk scene search
    │   ├── chat/             # v0.3: structured chat evidence
    │   │   └── ChatEvidenceList.tsx       # Structured evidence cards with normalizeEvidence()
    │   ├── document/         # v0.3: document metadata
    │   │   └── DocumentMetadataCard.tsx   # EPUB metadata display
    │   ├── topic/            # Topic detail sub-components
    │   │   ├── TopicHeader.tsx
    │   │   ├── ProviderBindingPanel.tsx
    │   │   ├── DocumentPanel.tsx          # TXT/EPUB upload + metadata
    │   │   ├── ParsePanel.tsx
    │   │   ├── ChaptersPanel.tsx          # Enhanced with source_href
    │   │   ├── EpubChapterTree.tsx        # v0.3: collapsible EPUB chapter tree
    │   │   ├── SourceLocatorBadge.tsx      # v0.3: inline source badge for chunks
    │   │   └── StoragePanel.tsx
    │   ├── provider/         # Provider config components
    │   │       ├── ProviderConfigForm.tsx
    │   │       └── EffectiveProviderConfigCard.tsx
    │   ├── works/            # v0.4: Work management
    │   │   ├── WorkList.tsx
    │   │   ├── WorkCard.tsx
    │   │   ├── WorkSelector.tsx
    │   │   ├── WorkDetail.tsx
    │   │   ├── WorkUploadPanel.tsx
    │   │   └── WorkAnalysisPanel.tsx
    │   ├── crossWork/        # v0.4: cross-work dashboard
    │   │   └── CrossWorkDashboard.tsx
    │   ├── entities/         # v0.4: global entity registry
    │   │   └── EntityRegistryTable.tsx
    │   ├── graphs/           # v0.4: character graph
    │   │   └── CharacterGraph.tsx
    │   ├── timeline/         # v0.4: timeline
    │   │   └── TimelineView.tsx
    ├── utils/                # Shared utilities
    │   └── format.ts         # formatBytes, formatDateTime, formatJsonPreview
    ├── components/           # Shared UI components
    │   ├── HealthPanel.tsx
    │   ├── AnalysisOutputCard.tsx
    │   ├── TokenRangeSlider.tsx
    │   ├── LoadingBlock.tsx
    │   ├── ErrorBlock.tsx
    │   ├── EmptyState.tsx
    │   └── StatusBadge.tsx
    ├── pages/                # Route page components
    │   ├── DashboardPage.tsx
    │   ├── ProvidersPage.tsx
    │   ├── TopicsPage.tsx
    │   ├── TopicDetailPage.tsx  # v0.4 tabs: Works, Dashboard, Entities, Graph, Timeline + Overview
    │   ├── TopicChatPage.tsx    # Chat sessions + structured evidence + config/usage right panel
    │   └── NotFoundPage.tsx
    ├── layouts/
    │   └── AppLayout.tsx
    └── styles/
        └── global.css
```

## Routes

| Path | Page | Description |
|------|------|-------------|
| `/` | DashboardPage | Health status + workflow overview |
| `/providers` | ProvidersPage | LLM provider CRUD |
| `/topics` | TopicsPage | Topic list + create |
| `/topics/:topicId` | TopicDetailPage | v0.4: Works, cross-work dashboard, entities, graph, timeline, v2 analysis, search, evidence |
| `/topics/:topicId/chat` | TopicChatPage | Chat sessions + structured evidence + config/usage right panel + source text viewer |
| `*` | NotFoundPage | 404 |

## v0.4 Features

### Multi-Work Management
- Tab navigation: Overview / Works / Entities / Graph / Timeline.
- Work CRUD: create, list, edit (title/subtitle/author/series_index/description), delete with 409 error display.
- Work selector: inline switcher when multiple Works exist.
- Work-scoped upload (TXT/EPUB), parse, and preview analysis buttons.
- Work detail: document metadata (filename, size, encoding), chapter/chunk counts.

### Cross-Work Dashboard
- Run/entity stats cards, last run status with error display.
- Build trigger button with auto-polling (2s interval) until terminal.
- Auto-detects existing running runs on page load.
- Terminal state invalidates entities/graph/timeline queries.
- Warnings display (up to 3, +N more).

### Entity Registry
- Search by name, filter by type, sort by mentions/name/confidence.
- Click-to-expand detail drawer: canonical name, aliases, work IDs, confidence, merge strategy.
- Mentions list with surface text and evidence snippets.

### Character Graph
- Edge table: source character → relation type → target character, with weight.
- Node/edge counts, snapshot metadata, empty state with build prompt.
- Error state for failed loads.

### Timeline
- Ordered event list: title, summary, participants, time label, sequence index, confidence.
- Empty state with build prompt, error state for failed loads.

## v0.3 Features

### EPUB Support
- Upload `.epub` files alongside `.txt`.
- EPUB Chapter Tree: collapsible, nav_order-sorted, with abbreviated source href.
- Source Locator Badge: green for EPUB, gray for TXT, with chapter/chunk info.
- Document Metadata Card: EPUB title, creator, language, publisher, identifier.

### Search & Retrieval
- Topic Search Panel: query input, FTS/Keyword Fallback method toggles, Enter-to-submit.
- Retrieval Debug Drawer: method checkboxes for all 5 retrieval methods, persisted trace.
- Retrieval Method Badge: 5 distinct colors (FTS, keyword_fallback, structured, analysis_output, semantic_rerank).

### Structured Chat Evidence
- Chat Evidence v3: structured cards (source_type, method, score, title, text, chunk_id).
- `normalizeEvidence()` backward-compatible with legacy `string[]`.
- "Open source" button for inline locator detail.

### Entity Evidence & Similar Scenes
- Entity Evidence Explorer: three sections (Atoms / Source Chunks / Related Outputs).
- Similar Scenes Panel: dual-mode (By Query / By Chunk ID) with ranked, scored results.

### Token Usage (v0.3.1)
- Run detail token breakdown: total / input / output / reasoning.
- `usage_unavailable_attempts` warning when API calls fail without returning usage.
- Cost estimate aligned with backend formula: `max_output_tokens × 0.65 × retry_multiplier`.
- Thinking mode adds 1.4× buffer to estimates.

## v0.2 Analysis Run

v0.2 introduces a staged analysis pipeline — Local Extraction → Deterministic Merge → Final Outputs — ~4× more token-efficient than v0.1.

### Frontend Features
- Chunks Meta + Range Selector
- Analysis Modes: Preview, Range, Full, Incremental
- Run Creation + Polling (2.5s interval)
- Run History (truncated to 10, expandable)
- Stage Progress with failure details
- Unified v1/v2 Output View
- Session Storage Run Persistence
- Cost Projection with effective config
- Error Recovery with retry on all panels

## Key Design Decisions

- **fetch over axios**: `apiRequest<T>()` handles base URL, JSON parsing, error handling, AbortSignal.
- **Plain CSS**: No Tailwind, no UI component library. Minimal, functional styles.
- **TanStack Query**: Server state (queries, mutations, cache invalidation, polling). No Redux/Zustand.
- **api_key never stored**: Frontend submits api_key on create but never persists it.
- **masked_api_key only**: Provider lists display `sk-...abcd`. Raw key never in responses.
- **Real LLM warnings**: Buttons for Provider Test, Run Analysis, and Send Message show API consumption warnings.
- **Chat page**: Collapsible 3-panel layout with draggable dividers. Message copy/edit/delete. Right panel: provider config, chat usage stats, source text viewer.
- **Optimistic updates**: User messages appear instantly via query cache manipulation with rollback.
- **Provider preset integration**: Base URL / Model dropdowns with manual override.

## Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `vite` | Start dev server with HMR |
| `build` | `tsc --noEmit && vite build` | Type-check then production build |
| `preview` | `vite preview` | Preview production build |
| `typecheck` | `tsc --noEmit` | TypeScript check only |
| `lint` | `eslint src/` | Lint source files |
| `check` | `npm run typecheck && npm run lint && npm run build` | All checks |
| `e2e` | `playwright test` | Run Playwright e2e tests (44 total) |
| `e2e:ui` | `playwright test --ui` | Run Playwright in UI mode |

## Dependencies

```json
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router-dom": "^7.15.0",
  "@tanstack/react-query": "^5.100.10"
}
```

Dev: `typescript`, `vite`, `@vitejs/plugin-react`, `eslint`, `typescript-eslint`, `@types/react`, `@types/react-dom`, `@playwright/test`.

## Forbidden (v0.4.0)

- Tailwind CSS or UI component libraries (MUI, Ant Design, Chakra)
- Redux, Zustand, MobX, or other state management beyond React Context + TanStack Query
- Next.js (SSR/SSG not needed for local-only tool)
- Axios (use fetch)
- Storing api_key in localStorage/sessionStorage
- Rendering full novel text in DOM (use preview/excerpt only)
