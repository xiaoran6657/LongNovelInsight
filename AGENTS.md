# AGENTS.md — LongNovelInsight Development Rules

## Project

LongNovelInsight is a local-first, single-user tool for LLM-assisted long-novel analysis.
The current release is **v0.4.0** and the active maintenance line is **v0.4.x**. ChatGPT Codex is
the primary engineering agent for ongoing maintenance and delivery.

## Sources of Truth

Read these files before non-trivial work, in this order:

1. `AGENTS.md` — stable engineering rules and scope boundaries.
2. `docs/SPEC.md` and `docs/ARCHITECTURE.md` — product and architecture contracts.
3. `docs/ROADMAP.md` — release direction; roadmap items are not automatically authorized.
4. `agent/PROJECT_STATUS.md` — last verified repository state.
5. `agent/NEXT_ACTIONS.md` — prioritized work queue.
6. `agent/HANDOFF.md` — current task ownership, evidence, and continuation notes.
7. `agent/DECISIONS.md` — append-only architecture decisions.

If documentation conflicts with running code or tests, verify the behavior, record the
discrepancy, and update the stale document in the same task.

## Current Product Boundary

- Backend: Python, FastAPI, SQLModel, SQLite; flat `backend/` structure.
- Frontend: React, TypeScript strict mode, Vite, TanStack Query, plain CSS.
- LLM: direct OpenAI-compatible HTTP API; DeepSeek is the default preset.
- Storage: local `data/` directory plus SQLite.
- Sources: TXT (normalized to UTF-8) and EPUB.
- Data model: a Topic contains multiple Works; each Work has at most one source Document.
- Runtime: Conda environment `LongNovelInsight` and local Node.js tooling.

## Forbidden in the v0.4 Line

Do not add:

1. Login, authentication, multi-user behavior, SaaS, cloud sync, or remote storage.
2. Multiple source documents per Work.
3. PDF parsing, OCR, or DRM removal.
4. Docker or container orchestration.
5. LangChain, LlamaIndex, or similar LLM frameworks.
6. Vector databases such as Chroma, Pinecone, Qdrant, or FAISS.
7. Redis, Celery, PostgreSQL, or message queues.
8. Plugin systems or extension marketplaces.
9. Tailwind, MUI, Ant Design, Chakra, Redux, Zustand, or MobX.
10. Complex abstractions or speculative extension points.

Do not implement v0.5+ roadmap work unless the user explicitly changes the active scope.

## Task and Agent Workflow

- Inspect before editing. Preserve unrelated user changes in a dirty worktree.
- For non-trivial work, maintain a short plan and assign one owner per file or subsystem.
- Parallel agents should begin with read-only audits or clearly disjoint write scopes.
- Before handoff, update `agent/HANDOFF.md` with scope, changed files, commands, results,
  open risks, and the exact next action.
- Update `agent/PROJECT_STATUS.md` only with facts verified in the current workspace.
- Keep `agent/NEXT_ACTIONS.md` prioritized and remove or archive completed detail.
- Append to `agent/DECISIONS.md` only for durable architectural or governance decisions.
- Conversation may be Chinese. Code, identifiers, documentation, and commit messages are English.

## Commands

```powershell
# Backend
cd backend
conda run -n LongNovelInsight python -m pytest -v
conda run -n LongNovelInsight ruff check .
conda run -n LongNovelInsight ruff format --check .
conda run -n LongNovelInsight python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
npm run dev
```

Tests that can mutate application state must use temporary databases and data directories.
Real LLM calls require explicit user intent and must never be part of the default test suite.

## Completion Checklist

- [ ] Relevant pytest tests pass; run the full backend suite for release-level changes.
- [ ] `ruff check .` passes in `backend/`.
- [ ] Frontend typecheck, lint, and production build pass.
- [ ] Relevant Playwright tests pass for user-visible workflow changes.
- [ ] No secrets, user data, databases, uploaded novels, or generated artifacts are tracked.
- [ ] No forbidden technology or out-of-scope feature was introduced.
- [ ] Project status, next actions, and handoff are updated when their facts changed.

## Git Authorization

- Never run `git add`, `git commit`, `git push`, create tags, or open pull requests without
  explicit user approval for that action.
- When staging is approved, stage only the intended files; never use broad staging by default.
- Never stage `data/`, databases, uploaded files, `.env`, API keys, caches, or build outputs.
- Commit messages use English imperative mood.

## Code Style

- Python: type hints on every function signature; Ruff formatting and lint rules apply.
- TypeScript: strict mode; prefer `type` over `interface`.
- Add comments or docstrings only when the reason is not evident from the code.
- Delete dead code instead of commenting it out.
- Prefer small domain modules and plain functions over framework-like abstractions.
- Do not add dependencies without explicit user approval.

## Repository Hygiene

- Product code belongs in `backend/` and `frontend/`.
- Durable documentation belongs in `docs/`; durable agent coordination belongs in `agent/`.
- One-off maintained utilities belong in `scripts/` and must document safety assumptions.
- Generated caches, build outputs, test reports, local databases, and uploaded sources remain
  ignored and may be deleted during cleanup when they contain no user data.
