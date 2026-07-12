# Current Handoff

## Objective

Complete `UI-002`: require explicit confirmation before a Work preview calls the configured LLM,
then hand the returned run ID to the existing status, persistence, cancellation, and output UI.

## Status

Verified on 2026-07-12 on branch `codex/repository-takeover`, based on published commit `07c8c5e`.
UI-002 implementation and tests are complete in the current working tree. Tags and releases are
not authorized.

## Ownership

- Primary agent: implementation, integration, verification, status, commit, and push.
- Frontend audit agent: component, persistence, and E2E design review.
- Backend audit agent: read-only Work run lifecycle and output-contract review.

## Changes

- Add a two-step confirmation that identifies the Work, three-chunk scope, real LLM call, and
  possible API-credit consumption before any create request is sent.
- Pass the created Work run ID into Topic-level persistence and switch to Overview so the shared
  run status, cancel/retry/resume, and filtered output panels take over.
- Refresh Work state when a run reaches terminal status and allow analyzed Works to be rerun.
- Reuse the existing strong analysis request/response types in the Work API client.
- Add mocked E2E coverage for no-request-before-confirmation, cancel safety, request body, run
  handoff, session persistence, and analyzed-Work reruns.

## Verification

- Typecheck and ESLint: pass.
- Production build: pass; 158 modules, 459.61 kB JS / 131.76 kB gzip.
- `npx playwright test e2e/v0.4-features.spec.ts`: 11 passed as part of the full run.
- `npm run e2e`: 49 passed in 17.1 seconds.
- Backend was not changed by UI-002; its last full baseline remains 725 passed.

## Notes

- The confirmation warns about API-credit consumption but cannot show a reliable numeric estimate;
  the backend currently exposes no Work estimate endpoint. `COST-001` tracks that follow-up.
- Work output metadata endpoints omit full content. The handoff intentionally uses the Topic output
  endpoint filtered by the exact run ID, which returns complete output content.
- Work runs are serialized at Topic scope. `start_immediately=false` is not used because the backend
  currently has no endpoint that starts such a pending run.

## Next Action

Start UI-003: normalize untrusted analysis JSON before rendering and add an output-area error
boundary.
