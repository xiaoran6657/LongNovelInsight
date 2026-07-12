# LongNovelInsight Development Workflow

This project is maintained as a continuous Codex-led engineering effort. A task may span
multiple agents and conversations, so repository evidence and explicit handoff notes are part
of the deliverable rather than optional bookkeeping.

## 1. Start a Task

1. Read `AGENTS.md`, `agent/PROJECT_STATUS.md`, `agent/NEXT_ACTIONS.md`, and
   `agent/HANDOFF.md`.
2. Check `git status` before editing and preserve unrelated changes.
3. Define a bounded outcome and acceptance checks.
4. Split parallel work only when file ownership is disjoint or the work is read-only.

## 2. Investigate

- Treat status documents as leads, not proof. Re-run relevant commands.
- Prefer repository code, tests, and current command output over historical prompts.
- Record contradictions between documentation and implementation before resolving them.
- Do not perform real LLM calls or mutate user data during routine diagnostics.

## 3. Implement

- Assign one agent as the owner of each file being edited.
- Keep changes within the current release scope.
- Add or update tests with behavior changes.
- Avoid dependencies and broad architecture changes unless the user explicitly approves them.

## 4. Verify

Use the quality gates in `AGENTS.md`. Release-level work requires the full backend suite,
backend lint, frontend typecheck, frontend lint, frontend build, and the applicable Playwright
suite. Write exact command results into `agent/PROJECT_STATUS.md` or `agent/HANDOFF.md`.

## 5. Hand Off

Before ending a work session, update `agent/HANDOFF.md` with:

- objective and current status;
- responsible agents or subsystem owners;
- changed files;
- commands and results;
- unresolved risks or decisions;
- the exact first action for the next session.

Keep `agent/NEXT_ACTIONS.md` as the prioritized queue, not a historical changelog. Durable
history belongs in release notes, architecture decisions, and Git history.

## 6. Git and Release Actions

Editing and local verification do not authorize staging or publication. `git add`, commits,
pushes, tags, pull requests, and releases each require explicit user approval. When approval is
given, stage only reviewed files and re-run the relevant quality gates before publishing.

## Completion Summary

Every completed task should report:

1. outcome and changed files;
2. commands run and exact results;
3. remaining risks or unverified behavior;
4. next recommended task;
5. whether any Git action still awaits approval.
