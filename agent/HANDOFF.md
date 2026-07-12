# Current Handoff

## Objective

Complete `UI-001`: make the Topic-level Work selector consistently scope the Entity Registry,
Character Graph, and Timeline, then preserve the behavior with mocked E2E coverage.

## Status

Verified on 2026-07-12 on branch `codex/repository-takeover`. The takeover commit `0fe8f10` is
published to `origin/codex/repository-takeover`. UI-001 implementation and tests are complete in
the current branch. Tags and releases are not authorized.

## Ownership

- Primary agent: implementation, integration, verification, status, commit, and push.
- Frontend audit agent: read-only component/query-key/E2E design review.
- Backend audit agent: read-only `work_id` contract and isolation coverage review.

## Changes

- Pass `activeWorkId` from `TopicDetailPage` to Entity, Graph, and Timeline components.
- Reset the selected Work when navigating between Topics.
- Include Work scope in each TanStack Query key and API request.
- Clear stale Entity detail selection when Work scope changes.
- Add three mocked E2E tests that distinguish All results from Work-scoped results.

## Verification

- `npm run check`: pass; 158 modules, 458.53 kB JS / 131.45 kB gzip.
- `npx playwright test e2e/v0.4-features.spec.ts`: 9 passed.
- `npm run e2e`: 47 passed in 17.8 seconds.
- Backend was not changed by UI-001; its last full baseline remains 725 passed.

## Notes

- Entity detail and mention endpoints remain Topic-global; only the Entity list is Work-filtered.
- Backend audit found weak GET filter assertions and a risk that a scoped cross-work build may
  become the latest snapshot shown by the All view. This is tracked separately and was not
  silently expanded into the frontend task.

## Next Action

Start UI-002: add explicit LLM cost confirmation and reliable run/result handoff to Work
analysis.
