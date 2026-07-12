# Project Status — LongNovelInsight

## Verified Snapshot

- **Verified:** 2026-07-12, Asia/Shanghai
- **Baseline commit:** `07c8c5e` on `codex/repository-takeover`
- **Branch:** `codex/repository-takeover`
- **Current increment:** UI-002 verified on 2026-07-12
- **Current development version:** `v0.4.0-dev`
- **Latest Git tag:** `v0.3.0` (`v0.3.1` and `v0.4.0` are not tagged)
- **Release state:** v0.4 implementation exists, but release validation is not complete

## Quality Baseline

### Backend

- Collection: 731 tests total; default configuration selects 725 and deselects 6 integration tests.
- Ruff: pass after takeover changes.
- Full pytest run: 725 passed, 6 integration tests deselected, in 327.91 seconds.
- Retrieval warning regression: 27 tests passed with SQLAlchemy warnings treated as errors.
- `beautifulsoup4 4.15.0` is installed from the declared project dependencies.
- No real LLM calls were made.
- Newly exposed and fixed under real SQLite foreign-key enforcement:
  - v0.4 Topic deletion omitted Work and cross-work derived rows;
  - chat deletion omitted RetrievalTrace rows;
  - document cleanup did not flush child rows before parents;
  - three retry tests used nonexistent chunk IDs;
  - an orphan provider-config test contradicted the schema foreign key;
  - EPUB content type depended on client MIME guessing.

### Frontend

- `npm ci`: pass; repaired a missing local Rollup optional binary.
- Typecheck: pass.
- ESLint: pass.
- Production build: pass, 158 modules, 459.61 kB JS / 131.76 kB gzip.
- Playwright discovery: 49 tests in 5 files.
- Full Playwright execution: 49 passed in 17.1 seconds.
- Security updates: Vite 6.4.3, React Router 7.18.1, Babel 7.29.7, js-yaml 4.3.0.
- `npm audit`: 0 vulnerabilities.

## Governance State

- Root `AGENTS.md` is the only stable agent rule source.
- `PROJECT_STATUS`, `NEXT_ACTIONS`, `HANDOFF`, and `DECISIONS` are versioned coordination files.
- The legacy `CLAUDE.md`, `.claude/`, `agent/runner/`, `agent/AGENT_RULES.md`, and historical
  development `Prompts/` were removed from the current workspace.
- The user authorized staging, commit, and push for `TAKEOVER-001`; tags and releases still
  require separate approval.

## Current Architecture Risks

- Three analysis concepts remain exposed: legacy outputs, jobs, and current analysis runs.
- In-process daemon threads lack a unified restart-recovery contract.
- Database migrations remain hand-written in `db.py`, though missing-column detection now
  propagates real database errors.
- Scoped cross-work builds may replace the latest snapshot used by the unfiltered All view;
  backend behavior and filter assertions need hardening.
- Work analysis has an API-credit confirmation but no backend numeric estimate endpoint yet.
- Analysis JSON rendering and chat edit-resend need resilience hardening.
- Several backend and frontend modules are large multi-agent conflict hotspots.

## Release Blockers

1. Complete the remaining P1 correctness tasks in `agent/NEXT_ACTIONS.md`.
2. Prepare final v0.4.0 release notes and request separate approval before tagging or releasing.
