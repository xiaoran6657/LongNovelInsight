# AGENTS.md — LongNovelInsight Development Rules

## Project

LongNovelInsight is a local-first LLM-powered long-novel analysis tool.
Current version: **v0.4.0-dev**.

## Tech Stack

- **Backend**: Python + FastAPI + SQLModel + SQLite. Flat structure: `main.py`, `config.py`, `db.py`, `routers/`, `models/`, `services/`, `tests/`. No `backend/app/` nesting.
- **Frontend**: React + TypeScript + Vite + TanStack Query
- **LLM**: OpenAI-Compatible API (DeepSeek by default)
- **Quality**: pytest + Ruff (backend), tsc + ESLint + Vite build (frontend)
- **Storage**: Local `data/` directory + SQLite. Uploaded .txt files are normalized to UTF-8.
- **Python env**: Conda environment `LongNovelInsight`
- **Key deps**: `fastapi`, `uvicorn`, `sqlmodel`, `httpx`, `python-multipart`, `pytest`, `ruff`

## Forbidden (v0.4.0)

Do NOT introduce or reference:
1. Login / auth / multi-user systems
2. Cloud sync / remote storage
3. Multiple source documents per Work
4. PDF parsing / OCR / DRM removal
5. Docker / containerization
6. LangChain / LLM frameworks
7. Vector databases (Chroma, Pinecone, Qdrant, FAISS, etc.)
8. Redis / Celery / PostgreSQL / message queues
9. Plugin systems
10. Complex abstractions or premature generalization
11. Any v0.5+ features (plugin marketplace, SaaS, remote storage)
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

## Git Rules

- **When invoked by the agent runner** (Phase B): Claude Code may commit as directed by the runner's explicit instructions.
- **In normal interactive mode**: NEVER run `git add`, `git commit`, or `git push` without explicit user request.
- Never commit `data/`, `*.sqlite`, `*.txt`, `.env`, or API keys.
- Commit messages in English, imperative mood.

## Code Style

- Python: type hints on all function signatures
- TypeScript: strict mode, prefer `type` over `interface`
- No docstrings unless the WHY is non-obvious
- No dead code, no commented-out blocks
- Flat over nested; simple over clever
