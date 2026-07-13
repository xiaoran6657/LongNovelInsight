# Project Status — LongNovelInsight

## Verified Snapshot

- **Verified:** 2026-07-13, Asia/Shanghai
- **Takeover baseline:** `3db6b68`; current publication branch: `codex/repository-takeover`
- **Branch:** `codex/repository-takeover`
- **Current increment:** REL-002 v0.4.0 version promotion, release commit, tag, and publication completed on 2026-07-13
- **Current release version:** `v0.4.0`
- **Latest Git tag:** `v0.4.0` (`v0.3.1` remains an untagged historical release record)
- **Release state:** v0.4.0 released from `codex/repository-takeover`

## Quality Baseline

### Backend

- Collection: 768 tests total; default configuration selects 762 and deselects 6 integration tests.
- Ruff lint and format checks: pass.
- Full pytest run: 762 passed, 6 integration tests deselected, in 348.67 seconds.
- Retrieval warning regression: 27 tests passed with SQLAlchemy warnings treated as errors.
- `beautifulsoup4 4.15.0` is installed from the declared project dependencies.
- `pip check`: no broken requirements.
- No real LLM calls were made.
- The default suite includes an isolated Work API smoke that uses temporary SQLite/files, executes
  the real AnalysisRun selection/merge/final stages, and mocks only the LLM extraction boundary.
- The authoritative AnalysisRun path is split behind a stable 662-line lifecycle facade into a
  518-line initial execution service and a 455-line retry/resume continuation service. Router and
  test compatibility entry points are unchanged.
- SQLite foreign-key enforcement is configured for every pooled connection during schema startup;
  it no longer depends on the v0.4 Document rebuild leaving one connection enabled.
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
- Production build: pass, 164 modules, 459.06 kB JS / 132.03 kB gzip.
- Playwright discovery: 53 tests in 6 files.
- Pure-logic unit suite: 17 passed in 1.3 seconds; no browser fixture.
- Full Playwright execution: 53 passed in 21.1 seconds.
- AnalysisOutputCard remains the stable public component but is reduced from 797 to 125 lines;
  data normalization, evidence primitives, and family renderers are isolated under the existing
  analysis feature boundary, with no new dependency.
- Security updates: Vite 6.4.3, React Router 7.18.1, Babel 7.29.7, js-yaml 4.3.0.
- `npm audit`: 0 vulnerabilities across 245 dependencies.

## Governance State

- Root `AGENTS.md` is the only stable agent rule source.
- `PROJECT_STATUS`, `NEXT_ACTIONS`, `HANDOFF`, and `DECISIONS` are versioned coordination files.
- The legacy `CLAUDE.md`, `.claude/`, `agent/runner/`, `agent/AGENT_RULES.md`, and historical
  development `Prompts/` were removed from the current workspace.
- Git staging, commit, push, tags, releases, and pull requests require explicit user approval.
- Current documentation has one authority per concern: runtime OpenAPI for exact HTTP schemas,
  `API.md` for the human endpoint map, `ARCHITECTURE.md` for runtime/storage boundaries,
  `ANALYSIS_RUN_CONTRACT.md` for lifecycle/deprecation, `LLM_PIPELINE.md` for external-call and
  usage behavior, and `DATA_MODEL.md` for persistence meaning.
- The API guide covers all 83 generated OpenAPI method/path operations with no missing or extra
  entries; all repository-local Markdown links pass the current link scan.
- The v0.4.0 release notes cover changes since the previous `v0.3.0` tag, upgrade behavior, known
  limitations, verification evidence, and publication state.

## Current Architecture Risks

- AnalysisRun is authoritative and the frontend exposes no legacy executor; deprecated Job/v1 APIs remain callable for v0.4 compatibility until an explicitly authorized removal task.
- AnalysisRun executor ownership is process-local; multiple backend processes sharing one SQLite database remain unsupported in v0.4.
- Database migrations are Engine-scoped and run through one ordered, replayable registry; a
  permanent version ledger remains intentionally deferred because Work/Chat steps also repair data.

- Work analysis estimates are token-based; currency estimates remain unavailable because provider pricing is not modeled.
- Legacy chat linkage backfill is deterministic but best-effort when historical rows have ambiguous ordering; new messages use explicit linkage and session-local turn order.
- Remaining large conflict hotspots include TopicChatPage, legacy analysis_service, merge_service,
  and ProvidersPage; the authoritative AnalysisRun path and AnalysisOutputCard are now partitioned.
- Pure tests cover analysis selection, formatting, and query-key matching; UI-adjacent normalization and run-state helpers remain future extraction candidates.

## Release Blockers

None for v0.4.0. Future v0.4.x work remains separately scoped in `agent/NEXT_ACTIONS.md` and
`docs/ROADMAP.md`.
