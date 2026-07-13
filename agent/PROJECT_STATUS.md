# Project Status — LongNovelInsight

## Verified Snapshot

- **Verified:** 2026-07-13, Asia/Shanghai
- **Release/main commit:** `057093c`; `main`, `origin/main`, and annotated tag `v0.4.0` resolve to
  the same commit
- **Working branch:** `codex/post-release-audit-fixes`
- **Current increment:** post-release correctness remediation for entity/graph integrity,
  Work-scoped analysis context, and multi-Work storage accounting
- **Working-tree state:** implementation, tests, and coordination updates are not committed or
  published
- **Current release version:** `v0.4.0`; active maintenance line: `v0.4.x`

## Current Remediation

- CROSS-001 was reopened after review. Entity rebuilds now reuse IDs for identity-equivalent groups
  and invalidate only retained graph snapshots whose node or edge references no longer resolve.
- Replayable startup migration `012_graph_snapshot_integrity` applies the same repair to pre-patch
  databases and rejects missing/duplicate node IDs, missing edge endpoints, endpoints absent from
  the node set, and node IDs absent from the live entity registry.
- Initial AnalysisRun execution, retry, and resume now resolve chapter titles through each selected
  Chunk's `chapter_id`; Topic-wide `chapter_index` collisions can no longer import another Work's
  title into the LLM context.
- `Topic.storage_bytes` is refreshed as the sum of all source Document sizes after TXT/EPUB upload,
  parse persistence, and document deletion. Migration `013_topic_storage_totals` backfills the same
  aggregate for every existing Topic during startup.
- Combination tests cover entities-only plus scoped-full graph retention, genuine entity removal,
  same-index chapters across Works, retry/resume, and multi-Work upload/parse/delete accounting.
- No real LLM request was made.

## Quality Baseline

### Backend

- Collection: 772 tests total; default configuration selects 766 and deselects 6 opt-in integration
  tests.
- Initial focused remediation suite: 107 passed in 53.14 seconds.
- Upgrade/integrity focused suite: 41 passed in 20.61 seconds.
- Full pytest: 766 passed, 6 deselected, in 351.90 seconds.
- `ruff check .`: pass.
- `ruff format --check .`: 137 files already formatted.
- The default suite uses temporary SQLite databases and data directories and mocks the external LLM
  boundary.

### Frontend

- No frontend source or dependency changed in this remediation.
- Latest v0.4.0 audit on the current release commit: typecheck, lint, 17 unit tests, production
  build, and 53 Playwright tests passed; npm audit reported zero vulnerabilities.

## Governance State

- Root `AGENTS.md` is the stable engineering rule source.
- Current product contracts are owned by `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/API.md`,
  `docs/DATA_MODEL.md`, `docs/ANALYSIS_RUN_CONTRACT.md`, and `docs/LLM_PIPELINE.md`.
- `PROJECT_STATUS`, `NEXT_ACTIONS`, `HANDOFF`, and append-only `DECISIONS` are versioned agent
  coordination records; completed v0.4.0 queue detail is archived under `agent/archive/`.
- Git staging, commit, push, tags, releases, and pull requests require explicit user approval.
- No v0.5 roadmap work, forbidden technology, dependency, or product-boundary expansion was added.

## Current Architecture Risks

- AnalysisRun executor ownership remains process-local; multiple backend processes sharing one
  SQLite database are unsupported in v0.4.
- Deprecated v1/Job analysis routes remain callable for compatibility until a separately authorized
  removal and migration task.
- Stable-ID overlap is the strongest entity continuity signal. Canonical-name and alias fallback is
  deterministic, but a real merge/split can remove an old ID and intentionally invalidate every
  graph snapshot that depended on it.
- Startup removes malformed or dangling graph snapshots instead of attempting to rewrite their
  evidence identities; users must rebuild a removed projection before it is available again.
- `Topic.storage_bytes` is an aggregate of persisted source Document sizes, not a filesystem quota
  scan; startup backfill trusts Document metadata rather than inspecting source files.

## Delivery State

The v0.4.0 published tag is unchanged. The post-release remediation passes all backend gates but is
not yet part of `main` or a v0.4.1 release. Review and explicit Git authorization are required before
staging, committing, or pushing it.
