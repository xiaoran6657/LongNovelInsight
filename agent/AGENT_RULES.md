# Agent Rules — LongNovelInsight

Rules for Claude Code when working on this project. These are more detailed operational constraints than CLAUDE.md; read both.

## Version Scope Lock

**Current version: v0.2.0-dev.** Backend pipeline complete. Frontend Steps 1–10 complete. Do NOT:

- Implement features from v0.3+ (EPUB, multi-book, graphs, vector search).
- Design abstractions "for future use."
- Add command-line flags, config options, or extension points that aren't needed now.
- Introduce Redis / Celery / PostgreSQL / Alembic / LangChain / vector DB.

When in doubt, re-read `Prompts/V0.2/Backend_Prompts.md` for the current step scope.

## Task Workflow

Every non-trivial task follows this cycle. Do NOT skip steps.

1. **Receive task** — I propose a task or requirement. You understand it and plan the approach.
2. **Implement** — Write code, run tests, run linter. Fix until all pass.
3. **Summarize** — Output: changed files, what was done, test results, risks, next steps. Do NOT ask about committing.
4. **I test** — I verify the changes locally in browser/terminal.
5. **I request commit** — Only when I explicitly say "commit" or "提交" do you run `git add` + `git commit`. If I don't mention commit, do NOT bring it up.
6. **Push** — After commit, try `git push` ONCE. If it fails (network/auth), tell me to push manually. Do NOT retry.

## Git Rules

- **NEVER run `git add`, `git commit`, or `git push` without my explicit request.**
- When I ask you to commit, stage only the relevant files (not `git add -A` or `git add .`).
- Try `git push` exactly once after commit. If it fails, stop and tell me.
- Commit messages in English, imperative mood.
- Never commit `data/`, `*.sqlite`, `*.txt`, `.env`, or API keys.

## What Must NEVER Be Committed

- `data/` directory and all contents
- `*.sqlite`, `*.sqlite3`, `*.db` files
- `*.txt` novel files
- `.env` files with API keys
- Any file containing a real API key or secret

These are already in `.gitignore`. Do NOT `git add -f` them.

## Environment

- **Always** assume the Conda environment is `LongNovelInsight`.
- Commands that need the environment should be prefixed or documented accordingly.

## Shell Command Rules

- **Never chain commands with `&&`, `;`, or `|`.** Each `Bash()` call must be a single, simple command.
- **Do NOT use `cd` in Bash commands.** Git works from any subdirectory. For Python tools, use the absolute path to the conda Python executable.
- **Why:** Compound commands like `cd * && git status` create unique permission strings for each directory combination. `cd g:/.../backend && git status` and `cd g:/.../frontend && git status` require separate approvals. Using `git status` directly works everywhere with one approval.

Examples of what NOT to do:
```
Bash(cd g:/Programming/LongNovelInsight/backend && git status)
Bash(cd g:/Programming/LongNovelInsight/backend && python -m pytest tests/ -v)
Bash(cd g:/Programming/LongNovelInsight/backend && python -m ruff check .)
```

Examples of what to do instead:
```
Bash(git status)
Bash("C:/Users/萧然/.conda/envs/LongNovelInsight/python.exe" -m pytest tests/ -v)
Bash("C:/Users/萧然/.conda/envs/LongNovelInsight/python.exe" -m ruff check .)
```

## Implementation Rules

1. **Plan first, code second.** Never start coding without a plan for non-trivial changes.
2. **Keep it simple.** Three similar lines beats a premature abstraction.
3. **No dead code.** Delete unused imports, variables, functions immediately.
4. **Type hints required.** All Python function signatures must have type hints. TypeScript is strict mode.
5. **No docstrings** on functions that are self-explanatory. Only add comments when the WHY is non-obvious.
6. **No emojis in code or docs** unless the user explicitly requests them.
7. **Chinese for conversation, English for code and commits.**

## Dependency Rules

- Do NOT add new dependencies without explicit user approval.
- Prefer stdlib over third-party packages.
- v0.1.0 explicitly forbids: `langchain`, `chromadb`, `pinecone-client`, `redis`, `celery`, `docker`, `psycopg2`.
- Do NOT use raw SQLAlchemy ORM directly; use SQLModel APIs for all database operations. (SQLAlchemy may appear as a transitive dependency of SQLModel — that is expected and acceptable.)

## File Organization

- Backend code goes in `backend/`.
- Frontend code goes in `frontend/`.
- Documentation goes in `docs/`.
- Agent context files go in `agent/`.
- Scripts (one-off, not part of the app) go in `scripts/`.

## Tool Caches

- All tool caches go under `.cache/` (unified location, ignored by git).
- Pytest: configured via `tool.pytest.ini_options.cache_dir` in `pyproject.toml`.
- Ruff: configured via `tool.ruff.cache-dir` in `pyproject.toml`.
- Do NOT create cache directories at the project root (e.g., `.ruff_cache/`, `.pytest_cache/`).

## When a Task Is Complete

1. Run backend tests (pytest). They must pass.
2. Run backend linter (ruff check). It must be clean.
3. Run frontend typecheck (tsc --noEmit). Must pass.
4. Run frontend lint (eslint). Must pass.
5. Run frontend build (vite build). Must pass.
6. Update `agent/PROJECT_STATUS.md`.
7. Update `agent/NEXT_ACTIONS.md`.
8. If an architecture decision was made, append to `agent/DECISIONS.md`.
9. Output the completion summary (changed files, commands, results, risks, next).
