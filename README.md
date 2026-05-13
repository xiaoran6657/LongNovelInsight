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

## Development

See [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md) for the development process with Claude Code.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the version roadmap.

## Backend Smoke Test

A live-server end-to-end test script is available at `backend/scripts/smoke_backend.py`. It exercises the full API flow against a running backend. See [docs/SMOKE_TEST.md](docs/SMOKE_TEST.md) for details.

```bash
# Quick safe-mode smoke test (no real LLM calls):
cd backend
python -m uvicorn main:app --reload --port 8000   # Terminal 1
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup  # Terminal 2
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
