# Next Actions

Statuses: `ready`, `in_progress`, `blocked`, `review`, `done`.

## P0 — Complete the v0.4.0-dev Baseline

| ID | Status | Owner | Task | Acceptance |
| --- | --- | --- | --- | --- |
| BASE-001 | done | primary | Install declared backend dependencies in Conda | `beautifulsoup4 4.15.0` installed on 2026-07-12 |
| BASE-002 | done | primary | Run full backend suite after BASE-001 | 725 passed; 6 integration tests deselected |
| BASE-003 | done | primary | Run full Playwright suite | 44 tests passed with mocked APIs on 2026-07-12 |
| BASE-004 | done | frontend | Upgrade vulnerable Vite and React Router versions | Frontend gates pass; npm audit reports 0 vulnerabilities |
| BASE-005 | done | primary | Review takeover diff and documentation links | Diff check and local Markdown link scan passed on 2026-07-12 |

## P1 — Correctness and User Trust

| ID | Status | Area | Task |
| --- | --- | --- | --- |
| UI-001 | ready | frontend | Wire active Work filtering into Entities, Graph, and Timeline query parameters and keys |
| UI-002 | ready | frontend/backend | Add cost confirmation and run/result handoff to Work analysis |
| UI-003 | ready | frontend | Normalize untrusted analysis JSON and add an output-area error boundary |
| CHAT-001 | ready | frontend/backend | Replace destructive edit-resend sequencing with an atomic or failure-safe flow |
| RUN-001 | ready | backend | Define one authoritative analysis-run path and a deprecation plan for jobs/legacy outputs |
| RUN-002 | ready | backend | Add startup recovery and single-executor guarantees for interrupted runs |

## P2 — Quality and Maintainability

| ID | Status | Area | Task |
| --- | --- | --- | --- |
| FE-TEST-001 | ready | frontend | Typecheck and lint E2E/config files; add pure-logic unit tests |
| FE-CACHE-001 | ready | frontend | Centralize TanStack Query key factories across Topic Detail and Chat |
| E2E-001 | ready | integration | Add isolated backend-integrated smoke coverage for Work upload/parse/analysis |
| DB-001 | ready | backend | Move hand-written migrations into ordered, tested migration functions with old-schema fixtures |
| DOC-001 | ready | docs | Consolidate current v0.4 API, architecture, and LLM pipeline documentation |
| REFACTOR-001 | ready | both | Split the largest service/components along existing domain boundaries without new frameworks |

## Later v0.4.x Candidates

- Interactive relationship graph visualization.
- Timeline pagination and evidence expansion.
- Work-scoped chat evidence filtering.
- Complete retry attempt-history merging.
- Narrow-window responsive layout and keyboard accessibility pass.

Roadmap items beyond v0.4 require explicit scope approval before implementation.
