# CLAUDE.md — LongNovelInsight Development Rules

## Project

LongNovelInsight is a local-first LLM-powered long-novel analysis tool.
Current version: **v0.2.0-dev**.

## Tech Stack

- **Backend**: Python + FastAPI + SQLModel + SQLite. Flat structure: `main.py`, `config.py`, `db.py`, `routers/`, `models/`, `services/`, `tests/`. No `backend/app/` nesting.
- **Frontend**: React + TypeScript + Vite + TanStack Query
- **LLM**: OpenAI-Compatible API (DeepSeek by default)
- **Quality**: pytest + Ruff (backend), tsc + ESLint + Vite build (frontend)
- **Storage**: Local `data/` directory + SQLite. Uploaded .txt files are normalized to UTF-8.
- **Python env**: Conda environment `LongNovelInsight`
- **Key deps**: `fastapi`, `uvicorn`, `sqlmodel`, `httpx`, `python-multipart`, `pytest`, `ruff`

## Forbidden (v0.2.0)

Do NOT introduce or reference:
1. Login / auth / multi-user systems
2. Cloud sync / remote storage
3. Multi-novel Topic (one Topic = one .txt)
4. .epub or PDF parsing
5. Docker / containerization
6. LangChain / LLM frameworks
7. Vector databases (Chroma, Pinecone, etc.)
8. Redis / Celery / PostgreSQL / message queues
9. Plugin systems
10. Complex abstractions or premature generalization
11. Any v0.3+ features (EPUB, multi-book, graphs, vector search)
12. Tailwind / MUI / Ant Design / Chakra / Redux / Zustand / MobX

## Commands

```bash
# Activate environment
conda activate LongNovelInsight

# Backend
cd backend
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run dev

# Tests
cd backend && pytest -v
cd frontend && npm run typecheck && npm run lint && npm run build

# Lint
cd backend && ruff check .
cd frontend && npx eslint src/

# Format
cd backend && ruff format .
cd frontend && npx prettier --write src/
```

## Pre-Commit Checklist

- [ ] pytest passes (backend)
- [ ] ruff check passes (backend)
- [ ] tsc --noEmit passes (frontend)
- [ ] eslint passes (frontend)
- [ ] vite build passes (frontend)
- [ ] No `data/`, `*.sqlite`, `*.txt` files staged
- [ ] No API keys or secrets in code
- [ ] No forbidden technologies introduced
- [ ] agent/PROJECT_STATUS.md updated

## Code Style

- Python: type hints on all function signatures
- TypeScript: strict mode, prefer `type` over `interface`
- No docstrings unless the WHY is non-obvious
- No dead code, no commented-out blocks
- Flat over nested; simple over clever

## Git

- Commit messages in English, imperative mood
- Never commit `data/`, `*.sqlite`, `*.txt`, `.env`, or API keys
- Co-authored-by: Claude <noreply@anthropic.com> on AI-assisted commits
