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
├── index.html                # Vite entry point
├── package.json              # React 18, Vite 6, TypeScript 5
├── vite.config.ts            # @vitejs/plugin-react, port 5173
├── tsconfig.json             # strict mode, ES2020, jsx react-jsx
├── eslint.config.js          # typescript-eslint + recommended
├── .env.example              # VITE_API_BASE_URL template
└── src/
    ├── vite-env.d.ts         # ImportMetaEnv type definitions
    ├── main.tsx              # React root render (QueryClient + Router)
    ├── router.tsx            # React Router route definitions ✅
    ├── api/                  # API client and endpoint modules
    │   ├── client.ts         # apiRequest<T>() with fetch ✅
    │   ├── types.ts          # Shared TypeScript types ✅
    │   └── health.ts         # GET /api/health ✅
    ├── components/           # Shared UI components
    │   └── HealthPanel.tsx   # Backend health status ✅
    ├── pages/                # Route page components
    │   ├── DashboardPage.tsx # Health + workflow overview ✅
    │   ├── ProvidersPage.tsx # Placeholder (Task 004)
    │   ├── TopicsPage.tsx    # Placeholder (Task 005)
    │   ├── TopicDetailPage.tsx # Placeholder (Task 006)
    │   ├── TopicChatPage.tsx # Placeholder (Task 008)
    │   └── NotFoundPage.tsx  # 404 ✅
    ├── layouts/              # Layout components
    │   └── AppLayout.tsx     # Header, nav, main, footer ✅
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
| `/topics/:topicId/chat` | TopicChatPage | Evidence-based chat |
| `*` | NotFoundPage | 404 |

## Key Design Decisions

- **fetch over axios**: Keep dependencies minimal. A thin `apiRequest<T>()` wrapper handles base URL, JSON parsing, and error handling.
- **Plain CSS**: No Tailwind, no UI component library. Styles are minimal and functional.
- **TanStack Query**: Used for server state management (queries, mutations, cache invalidation). Avoids manual `useEffect` + loading/error tracking.
- **api_key never stored**: The frontend submits api_key to the backend on create but never persists it in localStorage, sessionStorage, or state after form submission.
- **masked_api_key only**: Provider lists display `masked_api_key` (e.g., `sk-...abcd`). Raw `api_key` is never present in backend responses.
- **Real LLM warnings**: Buttons for Provider Test, Run Analysis, and Send Message display explicit warnings about API consumption.

## Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `vite` | Start dev server with HMR |
| `build` | `tsc -b && vite build` | Type-check then production build |
| `preview` | `vite preview` | Preview production build |
| `typecheck` | `tsc --noEmit` | TypeScript check only |
| `lint` | `eslint src/` | Lint source files |

## Dependencies

```json
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router-dom": "^6.x",
  "@tanstack/react-query": "^5.x"
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
