# Current Handoff

## Objective

Complete `CHAT-001`: replace destructive edit-then-delete chat resend with a failure-safe,
server-owned atomic replacement flow.

## Status

Verified on 2026-07-12 on branch `codex/repository-takeover`, based on published commit `d724059`.
CHAT-001 implementation and tests are complete in the current working tree. Tags and releases are
not authorized.

## Ownership

- Primary agent: implementation, integration, verification, status, commit, and push.
- Frontend audit agent: edit/resend failure-window, cache, editor, and E2E review.
- Backend audit agent: transaction, history, trace, locking, and concurrency review.

## Changes

- Add `POST /api/chat/sessions/{session_id}/messages/{message_id}/resend`, requiring the expected
  assistant ID and limiting edits to the latest complete exchange.
- Finish retrieval and LLM generation without a SQLite transaction, then acquire a write lock,
  revalidate the pair, and replace old messages/traces in one commit.
- Return 409 if another send changes the session during generation, 502 on LLM failure, and retain
  the original pair on all generation or commit failures.
- Exclude the replaced pair from LLM history so the old question/answer does not bias regeneration.
- Replace the frontend DELETE/sleep/POST sequence with the atomic endpoint; keep failed edits open,
  preserve revised text and the main draft, and show an API-credit/original-preserved warning.
- Add backend transaction/trace/history/concurrency regressions and mocked browser success/failure
  coverage.

## Verification

- Backend Ruff: pass.
- Backend chat tests: 30 passed.
- Backend full suite: 730 passed, 6 integration tests deselected, in 330.62 seconds.
- `npm run check`: pass; 159 modules, 461.71 kB JS / 132.58 kB gzip.
- Targeted chat E2E: 2 passed.
- `npm run e2e`: 52 passed in 25.0 seconds.

## Notes

- Only the latest complete exchange can be edited; changing an earlier turn without truncating later
  context would leave semantically inconsistent answers.
- The first post-LLM write is a conditional no-op update that serializes writers, followed by fresh
  expected-assistant/latest-pair validation before replacement.
- Message pairing still uses chronological adjacency. `CHAT-002` tracks explicit turn/reply IDs and
  stable ordering as a separate schema improvement.

## Next Action

Start `RUN-001`: define one authoritative analysis-run path and a deprecation plan for jobs and
legacy outputs before changing execution code.
