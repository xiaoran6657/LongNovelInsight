# LongNovelInsight — Development Workflow

This document describes how I (Claude Code) and the human developer collaborate on this project.

## Development Cycle

Every task follows this cycle:

1. **Plan** — Clarify the task scope. Read relevant existing code. Write a short plan. Wait for approval.
2. **Implement** — Write the code. Keep it simple. No over-engineering. Follow [CLAUDE.md](../CLAUDE.md) and [AGENT_RULES.md](../agent/AGENT_RULES.md).
3. **Test** — Run tests. Make sure they pass. Add new tests for new behavior.
4. **Fix** — Fix any test failures or lint errors. Repeat until clean.
5. **Update Agent Files** — Update `agent/PROJECT_STATUS.md` to reflect new state. Update `agent/NEXT_ACTIONS.md` with the next 3–5 tasks. If an architectural decision was made, append to `agent/DECISIONS.md`.
6. **Commit** — Commit with a clear English message. Do NOT commit `data/`, `*.sqlite`, `*.txt`, `.env`, or API keys.

## Task Completion Output

After every task (or logical sub-task), output a summary in this format:

```
### Changed Files
- path/to/file1.py — what changed
- path/to/file2.tsx — what changed

### Commands Run
```
pytest -v
ruff check .
```

### Test Results
- 12 passed, 0 failed
- ruff: no issues

### Risks / Notes
- Any potential issues to watch for
- Dependencies on future tasks

### Next Task
- The next thing to work on
```

## Communication

- Default language: Chinese (中文).
- Code and commit messages: English.
- When uncertain about scope, ask before implementing.
- Do not silently add features beyond the current task scope.

## Environment

- **Conda env**: `LongNovelInsight`
- **Backend port**: 8000
- **Frontend port**: 5173
- **Database**: `data/longnovelinsight.sqlite` (gitignored)
- **Data directory**: `data/` (gitignored)
