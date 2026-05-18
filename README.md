# LongNovelInsight

LongNovelInsight is a local-first tool that uses LLMs to analyze long novels (.txt format) and produce structured insights — character profiles, relationship maps, event timelines, causal chains, and thematic analysis — all stored on your own machine.

## v0.1.0

### What It Does

- Open a browser at localhost and configure an LLM provider (DeepSeek or any OpenAI-compatible API). Provider can be added before or after creating a Topic.
- Create a Topic, optionally bind a provider, and upload one `.txt` novel file.
- Automatically split the novel into chapters and chunks, with token/word/disk-usage statistics.
- Call the LLM to generate:
  - **Work overview** — summary, style, narrative structure.
  - **Character list** — profiles with evidence-backed traits.
  - **Character relationships** — typed relationships between characters.
  - **Key events** — chronological list of major plot events.
  - **Event causal chain** — how events lead to one another.
  - **Theme / philosophy analysis** — identified themes and philosophical ideas.
- Ask free-form questions within a Topic; answers are grounded in the existing analysis and relevant source chunks.
- All data (novels, analysis, chat history) is stored locally in `data/` and SQLite.
- Delete any Topic, its original text, analysis results, and chat history at any time.
- View storage usage, task progress, and analysis status in the frontend.

### What It Does NOT Do (v0.1.0)

- No login system. No multi-user support.
- No cloud sync. Everything stays on your machine.
- No multi-novel cross-analysis. One Topic = one `.txt` novel.
- No `.epub` or PDF support — `.txt` only.
- No Docker, no Redis, no Celery, no PostgreSQL.
- No LangChain, no vector databases, no plugin system.

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

### Backend (automated script)

A live-server end-to-end test script is at `backend/scripts/smoke_backend.py`. See [docs/SMOKE_TEST.md](docs/SMOKE_TEST.md) for details.

```bash
# Quick safe-mode smoke test (no real LLM calls):
cd backend
python -m uvicorn main:app --reload --port 8000   # Terminal 1
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup  # Terminal 2
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
