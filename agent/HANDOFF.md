# Current Handoff

## Objective

Remediate the post-v0.4.0 audit and follow-up persistence findings without widening the v0.4.x
product boundary: preserve evidence-linked graph references across rebuilds and upgrades, isolate
AnalysisRun chapter titles by Work, aggregate Topic storage across Works for new and existing data,
and refresh stale coordination state.

## Status

Implementation and documentation are complete, all backend quality gates pass, and implementation
commit `8eb25fa` is published on both `main` and `codex/post-release-audit-fixes`. The `v0.4.0` tag
remains unchanged. No real LLM request was made.

## Changed Scope

- `backend/services/cross_work_entity_service.py`: reuse identity-equivalent GlobalEntity IDs,
  persist stable-ID metadata, and invalidate retained graph snapshots with malformed or missing
  entity references.
- `backend/services/analysis_run_execution_service.py` and
  `backend/services/analysis_run_continuation_service.py`: use chunk-to-chapter identity for initial,
  retry, and resume prompt titles.
- `backend/services/document_service.py` and `backend/services/parser_service.py`: recalculate the
  Topic source-byte aggregate after every relevant document mutation.
- `backend/migrations.py`: append replayable graph-integrity and Topic-storage backfill migrations.
- `backend/tests/test_migrations.py`, `test_v04_graph.py`, `test_v04_entities.py`,
  `test_v04_analysis.py`, `test_analysis_runs.py`, and `test_v04_upload_parse.py`: add pre-patch
  upgrade fixtures, strict malformed-record checks, and orchestration-level regressions.
- `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, and `agent/DECISIONS.md`: document the entity ID
  continuity and dependent-snapshot invalidation contract.
- `agent/PROJECT_STATUS.md`, `agent/NEXT_ACTIONS.md`, and `agent/archive/v0.4.0_COMPLETED.md`: record
  the actual branch/main state, archive the release queue, and expose new v0.4.x candidates.

## Verification

Run from `backend/` unless noted:

- Initial focused services and tests: Ruff lint/format pass; 107 tests passed in 53.14 seconds.
- Upgrade/integrity focused services and tests: Ruff lint/format pass; 41 tests passed in 20.61
  seconds.
- `conda run -n LongNovelInsight ruff check .`: pass.
- `conda run -n LongNovelInsight ruff format --check .`: 137 files already formatted.
- `conda run -n LongNovelInsight python -m pytest -v`: 766 passed, 6 deselected, in 351.90 seconds.
- Frontend gates were not rerun because no frontend file or dependency changed; the v0.4.0 audit
  baseline on commit `057093c` remains typecheck/lint/build/unit/Playwright clean.

## Open Risks

- Entity continuity fallback by normalized canonical name or alias is necessarily heuristic. Stable
  IDs take priority, matching is deterministic, and any unmatched old reference causes snapshot
  invalidation rather than silent dangling data.
- Startup deletes invalid persisted graph projections rather than fabricating entity mappings. The
  underlying entities and evidence remain intact, but a deleted projection must be rebuilt before
  graph GET can return it.
- Storage backfill uses persisted Document byte metadata and does not reconcile missing or manually
  altered source files on disk.
- The published `v0.4.0` tag does not contain these fixes and must remain immutable. Any maintenance
  release promotion requires a separately authorized release task.

## Exact Next Action

Select and explicitly authorize one `ready` v0.4.x item from `agent/NEXT_ACTIONS.md`. Do not begin
v0.5 work or promote a v0.4.1 release without an explicit scope change and release authorization.
