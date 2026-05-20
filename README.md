# LongNovelInsight

LongNovelInsight is a local-first tool that uses LLMs to analyze long novels (.txt format) and produce structured insights — character profiles, relationship maps, event timelines, causal chains, and thematic analysis — all stored on your own machine.

## v0.2.0-dev (current)

Backend v0.2 is complete (Steps 1–13). The frontend has not yet been updated for v0.2; it still uses the v0.1 analysis API. v0.2 introduces a staged analysis pipeline that is ~4× more token-efficient.

### What's New in v0.2 Backend

- **Staged analysis pipeline**: Per-chunk `local_extraction` (LLM) → `deterministic merge` (Python) → `final outputs` (Python). Each chunk is sent to the LLM once instead of 6 times.
- **8 atom types**: characters, events, relations, causal links, theme signals, worldbuilding, foreshadowing, open questions — all with stable IDs, evidence quotes, and source tracking.
- **Analysis modes**: `preview`, `range`, `full`, `incremental` — flexible chunk selection.
- **Retry & resume**: Failed chunks can be retried. Interrupted runs can be resumed.
- **Hybrid storage**: Large analysis JSON is stored on disk (under `data/topics/{id}/artifacts/`); small JSON stays inline in SQLite.
- **Active-run guard**: Prevents duplicate concurrent analysis runs for the same Topic.
- **Legacy bridge**: Existing v0.1 endpoints (`/analysis/run`, `/analysis/outputs`) still work. `pipeline=v2` parameter on legacy endpoints delegates to v2.

### What It Does NOT Do (v0.2.0-dev)

- Same restrictions as v0.1, plus:
- Frontend has NOT been updated for v0.2. The UI still shows v0.1 analysis cards.
- No EPUB/PDF parsing, no multi-novel cross-analysis, no vector DB, no Docker.

### You Bring Your Own API Key

LongNovelInsight is a local tool. You provide your own LLM API key (DeepSeek or any OpenAI-compatible provider). Your key stays on your machine and is never sent anywhere else.

### Copyright Notice

**Do not upload copyrighted novels that you do not have the rights to.** This tool is designed for analyzing public domain works, your own original writing, or works you are legally authorized to process. The repository itself does not contain any novel text.

## Tech Stack

| Layer    | Technology                          |
| -------- | ----------------------------------- |
| Backend  | Python + FastAPI + SQLModel + SQLite |
| Frontend | React + TypeScript + Vite           |
| LLM      | OpenAI-Compatible API (DeepSeek by default) |
| Quality  | pytest + Ruff                       |
| Storage  | Local `data/` directory + SQLite    |

## Quick Start

```bash
# Terminal 1 — Backend (Python + FastAPI)
cd backend
conda activate LongNovelInsight
pip install -e ".[dev]"
python -m uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/health

# Terminal 2 — Frontend (React + TypeScript + Vite)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Set your API key before running real LLM analysis or chat:

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
# Linux / macOS / Git Bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

## Development

See [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md) for the development process with Claude Code.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the version roadmap.

## Smoke Tests

### Frontend (manual walkthrough)

A step-by-step manual smoke test covering the full product workflow (health, provider, topic, upload, parse, analysis, chat, cleanup) is at [docs/FRONTEND_SMOKE_TEST.md](docs/FRONTEND_SMOKE_TEST.md). Run through it after any significant frontend change.

### Backend (automated scripts)

v0.1 smoke test at `backend/scripts/smoke_backend.py`. v0.2 smoke test at `backend/scripts/smoke_v2_backend.py`. See [docs/SMOKE_TEST.md](docs/SMOKE_TEST.md) for details.

```bash
# v0.1 safe-mode smoke test (no real LLM calls):
cd backend
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup

# v0.2 safe-mode smoke test:
python scripts/smoke_v2_backend.py --base-url http://127.0.0.1:8000 --cleanup
```

## v0.1.0 Feature Checklist

### Provider Management
- [x] Create provider with preset (DeepSeek/OpenAI/Qwen/Moonshot/Custom)
- [x] Base URL and model dropdowns auto-populate from preset
- [x] Manual base URL and model name editing
- [x] Optional advanced fields (context window, max tokens, temperature)
- [x] API key masked in list (`sk-...abcd`), never returned by API
- [x] Connection test with API consumption warning
- [x] Edit / delete provider (blocked if bound to a Topic)

### Topic Management
- [x] Create / list / detail / delete Topic
- [x] Bind / re-bind Provider
- [x] Document upload (.txt, UTF-8/GBK/GB18030/UTF-16 → UTF-8)
- [x] Delete document with full cascade

### Parse & Storage
- [x] Parse novel → chapters + overlapping chunks
- [x] View chapters list with titles and char counts
- [x] View chunks with text preview toggle
- [x] Storage breakdown (novel / chunks / analyses / DB)
- [x] Idempotent: re-parse returns existing results unless forced
- [x] Whitespace normalization (excessive blank lines collapsed)

### Analysis
- [x] Run structured analysis (6 types via async parallel jobs)
- [x] Adjustable limit_chunks with token cost estimate
- [x] Provider Config panel: Model / Max Tokens / Temperature / Thinking with presets
- [x] Model recommendation based on document size (Fast / Quality presets)
- [x] Per-type output cards with evidence, confidence, source chunk IDs
- [x] Retry failed types / Re-analyze with deepen mode
- [x] Progress bar with per-type completion polling
- [x] Summary bar: elapsed time, real token usage, per-type status

### Chat
- [x] Session CRUD with collapsible sidebar
- [x] Evidence-grounded Q&A with retrieval context
- [x] Multi-turn conversation history (last 6 messages)
- [x] Message actions: copy, inline edit & resend, delete
- [x] Optimistic user message display
- [x] Auto-height input with distinct background
- [x] Collapsible right panel with draggable dividers
- [x] Right panel: editable Provider Config + per-model usage stats
- [x] Right panel: source text viewer
- [x] Token usage tracked per message (prompt / completion / total) by model

## License

AGPL-3.0 — see [LICENSE](LICENSE).
