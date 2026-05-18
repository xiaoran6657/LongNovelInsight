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
├── tsconfig.json             # strict mode, ES2020, jsx react-jsx
├── eslint.config.js          # typescript-eslint + recommended
├── .env.example              # VITE_API_BASE_URL template
└── src/
    ├── vite-env.d.ts         # ImportMetaEnv type definitions
    ├── main.tsx              # React root render (QueryClient + Router)
    ├── router.tsx            # React Router route definitions
    ├── api/                  # API client and endpoint modules
    │   ├── client.ts         # apiRequest<T>() with fetch
    │   ├── types.ts          # Shared TypeScript types
    │   ├── health.ts         # GET /api/health
    │   ├── providers.ts      # Provider CRUD + test + presets
    │   ├── topics.ts         # Topic CRUD + provider config + effective config + recommendation
    │   ├── documents.ts      # Document upload / delete
    │   ├── parse.ts          # Parse / chapters / chunks / storage
    │   ├── analysis.ts       # Analysis run / outputs / jobs / status
    │   └── chat.ts           # Chat sessions / messages / delete message
    ├── utils/                # Shared utilities
    │   └── format.ts         # formatBytes, formatDateTime, formatJsonPreview
    ├── components/           # Shared UI components
    │   ├── HealthPanel.tsx   # Backend health status
    │   ├── AnalysisOutputCard.tsx  # Type-specific analysis output rendering
    │   ├── LoadingBlock.tsx  # Standard loading state
    │   ├── ErrorBlock.tsx    # Standard error state (with retry)
    │   ├── EmptyState.tsx    # Standard empty state (with action)
    │   └── StatusBadge.tsx   # Color-coded status label
    ├── pages/                # Route page components
    │   ├── DashboardPage.tsx # Health + workflow overview
    │   ├── ProvidersPage.tsx # LLM provider CRUD + presets + flexible fields
    │   ├── TopicsPage.tsx    # Topic list + create
    │   ├── TopicDetailPage.tsx # Document, parse, analysis, provider config, storage
    │   ├── TopicChatPage.tsx # Chat sessions + evidence Q&A + copy/edit/delete + right panel
    │   └── NotFoundPage.tsx  # 404
    ├── layouts/              # Layout components
    │   └── AppLayout.tsx     # Header, nav, main, footer
    └── styles/
        └── global.css        # Global styles
```

## Routes

| Path | Page | Description |
|------|------|-------------|
| `/` | DashboardPage | Health status + workflow overview |
| `/providers` | ProvidersPage | LLM provider CRUD |
| `/topics` | TopicsPage | Topic list + create |
| `/topics/:topicId` | TopicDetailPage | Document, parse, analysis |
| `/topics/:topicId/chat` | TopicChatPage | Chat sessions + evidence Q&A + config/usage right panel + source text viewer |
| `*` | NotFoundPage | 404 |

## Analysis Token Cost

v0.1 structured analysis (Run Analysis) makes independent LLM calls for each of the 6 output types (overview, characters, relations, events, causality, themes). The selected chunk text is sent repeatedly — once per type. Each call also includes a system prompt and generates structured JSON output.

For example, with N selected chunks totalling ~14,000 characters:
- Per-type input: ~4,000 text tokens + ~600 prompt tokens
- Total input: 6 × ~4,600 = ~27,600 tokens
- Estimated output: 6 × ~800 = ~4,800 tokens

**Recommendation**: Test with small `limit_chunks` values first (1–3) before running on larger selections.

## Key Design Decisions

- **fetch over axios**: Keep dependencies minimal. `apiRequest<T>()` handles base URL, JSON parsing, error handling, AbortSignal, and empty response.
- **Plain CSS**: No Tailwind, no UI component library. Styles are minimal and functional.
- **TanStack Query**: Used for server state management (queries, mutations, cache invalidation).
- **api_key never stored**: The frontend submits api_key to the backend on create but never persists it in localStorage, sessionStorage, or state after form submission.
- **masked_api_key only**: Provider lists display `masked_api_key` (e.g., `sk-...abcd`). Raw `api_key` is never present in backend responses.
- **Real LLM warnings**: Buttons for Provider Test, Run Analysis, and Send Message display explicit warnings about API consumption.
- **Chat page features**: Collapsible 3-panel layout (sessions sidebar, messages, right panel) with draggable dividers. Message actions: copy to clipboard, inline edit & resend, delete with confirmation. Right panel tabs: editable Provider Config (Model/Max Tokens/Temperature/Thinking) with long-press stepper, per-model Chat Usage stats (real token data from LLM responses), and Source text viewer.
- **Optimistic updates**: User messages appear instantly in chat via query cache manipulation with rollback on error.
- **Provider preset integration**: Base URL / Model dropdowns with manual override on both Providers and Topic config pages.

## Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `vite` | Start dev server with HMR |
| `build` | `tsc --noEmit && vite build` | Type-check then production build |
| `preview` | `vite preview` | Preview production build |
| `typecheck` | `tsc --noEmit` | TypeScript check only |
| `lint` | `eslint src/` | Lint source files |
| `check` | `npm run typecheck && npm run lint && npm run build` | All checks |

## Dependencies

```json
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router-dom": "^7.15.0",
  "@tanstack/react-query": "^5.100.10"
}
```

Dev dependencies: `typescript`, `vite`, `@vitejs/plugin-react`, `eslint`, `typescript-eslint`, `@types/react`, `@types/react-dom`.

## Forbidden (v0.1.0)

- Tailwind CSS or UI component libraries (MUI, Ant Design, Chakra)
- Redux, Zustand, MobX, or other state management beyond React Context + TanStack Query
- Next.js (SSR/SSG not needed for local-only tool)
- Axios (use fetch)
- Storing api_key in localStorage/sessionStorage
- Rendering full novel text in DOM (use preview/excerpt only)
