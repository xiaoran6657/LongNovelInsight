# Current Handoff

## Objective

Complete REL-002 by promoting final v0.4.0 version metadata, revalidating the release candidate,
creating and pushing the release commit and annotated tag, and publishing the GitHub Release after
the user's explicit authorization.

## Status

REL-002 completed on 2026-07-13. v0.4.0 is published from `codex/repository-takeover`, the
annotated `v0.4.0` tag identifies the release commit, and the GitHub Release is public at
`https://github.com/xiaoran6657/LongNovelInsight/releases/tag/v0.4.0`.

The release commit contains the previously uncommitted CHAT-002, E2E-001, DB-001, DOC-001,
REFACTOR-001, REL-001, and REL-002 work. No real LLM request was made.

## Ownership

- Primary agent: final version promotion, release documentation, complete quality gates, explicit
  staging review, commit, branch/tag push through the configured proxy, GitHub Release, and handoff.
- No subagents were used for REL-002.

## Release Contents

- Explicit chat turn/reply linkage, stable ordering, and deterministic legacy backfill.
- Isolated backend-integrated Work upload/parse/AnalysisRun smoke coverage.
- Ordered, replayable, Engine-scoped SQLite migrations with old-schema fixtures.
- Consolidated current API, architecture, data, frontend, and LLM pipeline documentation.
- AnalysisRun lifecycle/execution/continuation service boundaries and split analysis-output
  renderers with pure-logic coverage.
- Final `0.4.0` backend/frontend/health/package/test/documentation identifiers.
- v0.4.0 release notes, upgrade guidance, known limitations, and verified release evidence.

## Final Verification

### Backend

- `conda run -n LongNovelInsight python -m pytest -v`: 762 passed, 6 integration tests deselected
  in 348.67 seconds.
- `conda run -n LongNovelInsight ruff check .`: pass.
- `conda run -n LongNovelInsight ruff format --check .`: 137 files already formatted.
- `conda run -n LongNovelInsight python -m pip check`: no broken requirements.

### Frontend

- `npm run check`: typecheck, ESLint, 17 pure-logic tests, and production build pass.
- Unit suite: 17 passed in 1.3 seconds.
- Production build: 164 modules, 459.06 kB JS / 132.03 kB gzip.
- `npm run e2e`: 53 passed in 21.1 seconds.
- `npm audit --audit-level=low`: 0 vulnerabilities across 245 dependencies.

### Release Hygiene

- All maintained current-version declarations resolve to `0.4.0`.
- Runtime OpenAPI and `docs/API.md` match across 83 method/path operations.
- Repository-local Markdown links, tracked data paths, product/document secrets, forbidden source
  dependencies, generated artifacts, conflict markers, unmerged paths, and patch whitespace pass.
- The only key-shaped repository match is an intentional masked test fixture.
- All 13 previously untracked files were reviewed as intended release files before staging.

## Known Limitations

- AnalysisRun executor ownership is process-local; multiple backend processes sharing one SQLite
  database remain unsupported.
- Deprecated v1/Job analysis routes remain callable for compatibility.
- Relationship visualization remains an edge table and timeline pagination is deferred.
- Browser E2E uses mocked APIs; the backend suite contains the default-safe integrated Work smoke.
- The opt-in live-provider smoke was not run because it can spend real provider credit.

## Next Action

No v0.4.0 release blocker remains. Select and explicitly authorize a later v0.4.x candidate from
`agent/NEXT_ACTIONS.md`, or begin a separately scoped v0.4.1 maintenance plan. Do not start v0.5
roadmap work without the user's explicit scope change.
