# Project Status — LongNovelInsight

## Verified Snapshot

- **Verified:** 2026-07-13, Asia/Shanghai
- **Takeover baseline:** `3db6b68`; current publication branch: `codex/repository-takeover`
- **Branch:** `codex/repository-takeover`
- **Current increment:** FE-CACHE-001 centralized Topic Detail/Chat query keys completed on 2026-07-13
- **Current development version:** `v0.4.0-dev`
- **Latest Git tag:** `v0.3.0` (`v0.3.1` and `v0.4.0` are not tagged)
- **Release state:** v0.4 implementation exists, but release validation is not complete

## Quality Baseline

### Backend

- Collection: 761 tests total; default configuration selects 755 and deselects 6 integration tests.
- Ruff lint and format checks: pass.
- Full pytest run: 755 passed, 6 integration tests deselected, in 329.66 seconds.
- Retrieval warning regression: 27 tests passed with SQLAlchemy warnings treated as errors.
- `beautifulsoup4 4.15.0` is installed from the declared project dependencies.
- `pip check`: no broken requirements.
- No real LLM calls were made.
- Newly exposed and fixed under real SQLite foreign-key enforcement:
  - v0.4 Topic deletion omitted Work and cross-work derived rows;
  - chat deletion omitted RetrievalTrace rows;
  - document cleanup did not flush child rows before parents;
  - three retry tests used nonexistent chunk IDs;
  - an orphan provider-config test contradicted the schema foreign key;
  - EPUB content type depended on client MIME guessing.
  - Topic AnalysisRun creation could mix chunks from multiple Works before default-Work resolution.
  - orphaned running AnalysisRuns remained active after restart and duplicate service starts could launch competing executors.
  - scoped cross-work builds could replace canonical All entity, graph, and timeline materializations.

### Frontend

- `npm ci`: pass; repaired a missing local Rollup optional binary.
- Typecheck: pass across source, E2E, unit tests, and Vite/Playwright configs.
- ESLint: pass across source, E2E, unit tests, and maintained config files.
- Production build: pass, 159 modules, 458.98 kB JS / 131.99 kB gzip.
- Playwright discovery: 53 tests in 6 files.
- Pure-logic unit suite: 12 passed in 1.4 seconds; no browser fixture.
- Full Playwright execution: 53 passed in 18.1 seconds.
- Security updates: Vite 6.4.3, React Router 7.18.1, Babel 7.29.7, js-yaml 4.3.0.
- `npm audit`: 0 vulnerabilities across 245 dependencies.

## Governance State

- Root `AGENTS.md` is the only stable agent rule source.
- `PROJECT_STATUS`, `NEXT_ACTIONS`, `HANDOFF`, and `DECISIONS` are versioned coordination files.
- The legacy `CLAUDE.md`, `.claude/`, `agent/runner/`, `agent/AGENT_RULES.md`, and historical
  development `Prompts/` were removed from the current workspace.
- Git staging, commit, push, tags, releases, and pull requests require explicit user approval.

## Current Architecture Risks

- AnalysisRun is authoritative and the frontend exposes no legacy executor; deprecated Job/v1 APIs remain callable for v0.4 compatibility until an explicitly authorized removal task.
- AnalysisRun executor ownership is process-local; multiple backend processes sharing one SQLite database remain unsupported in v0.4.
- Database migrations remain hand-written in `db.py`, though missing-column detection now
  propagates real database errors.

- Work analysis estimates are token-based; currency estimates remain unavailable because provider pricing is not modeled.
- Chat pair association still relies on timestamps rather than explicit turn/reply IDs.
- Several backend and frontend modules are large multi-agent conflict hotspots.
- Pure tests cover analysis selection, formatting, and query-key matching; UI-adjacent normalization and run-state helpers remain future extraction candidates.

## Release Blockers

1. Complete the remaining P1 correctness tasks in `agent/NEXT_ACTIONS.md`.
2. Prepare final v0.4.0 release notes and request separate approval before tagging or releasing.
