# Authoritative Analysis Run Contract

This document defines the current v0.4 analysis execution authority and the compatibility boundary
for older local databases and API clients.

## Authoritative Path

AnalysisRun and services/analysis_run_service.py are the only supported execution lifecycle for
new product code.

| Concern | Authoritative contract |
| --- | --- |
| Work creation | POST /api/works/{work_id}/analysis/runs |
| Topic creation facade | POST /api/topics/{topic_id}/analysis/runs; resolves the deterministic default Work before creating the run |
| Status | GET /api/analysis/runs/{run_id} |
| Control | POST /api/analysis/runs/{run_id}/cancel, /retry-failed, /resume |
| Execution record | AnalysisRun |
| LLM stage | One LocalExtraction per selected chunk and run |
| Structured facts | ExtractedAtom linked to the run extraction |
| Final projection | AnalysisOutput with non-null run_id |

Both creation routes enter the same service and lifecycle. The Work route is the explicit v0.4
path. The Topic facade exists for the Overview UI and legacy single-document clients; on a
multi-Work Topic it selects only the default Work, never chunks from multiple Works.

AnalysisOutput remains a current read model used by the UI, retrieval, chat, merge, and final
stages. The table and GET /analysis/outputs are not deprecated. A non-null run_id is current
execution provenance; a null run_id identifies a historical v1/job-era output.

## Executor Ownership and Restart Recovery

Analysis executors are process-local daemon threads coordinated by one service-owned registry:

- At most one registered executor may own a Topic at a time.
- The same run cannot be started twice while its executor is registered.
- Initial start, retry-failed, and resume validate and claim executor ownership in the service layer
  before launching a thread.
- Creating a run is serialized with the active-run and executor checks.
- Executor ownership is always released when its target exits; thread-start failures mark the run
  failed and release the claim.

On backend startup, persisted running rows have no surviving thread and are marked failed with
structured startup_recovery metadata and an explicit-resume message. Persisted pending rows are
left unchanged because start_immediately=false is an intentional user state. Startup recovery
never makes an LLM call. The user resumes an interrupted run through
POST /api/analysis/runs/{run_id}/resume; succeeded chunk extractions remain idempotently reusable.

This is a single-process guarantee for the supported local deployment. Running multiple backend
worker processes against the same SQLite database is outside the v0.4 runtime contract.

## Deprecated Executors

The following operations remain callable in v0.4 for compatibility but are marked deprecated in
the generated OpenAPI document and must not receive new frontend callers:

- POST /api/topics/{topic_id}/analysis/run, including the pipeline=v2 bridge.
- POST /api/topics/{topic_id}/analysis/run-async.
- POST /api/topics/{topic_id}/analysis/run/{output_type}.
- All /api/topics/{topic_id}/analysis/jobs, /api/topics/{topic_id}/analysis/status, and
  /api/analysis/jobs/{job_id} operations.

These are independent executors, not adapters over AnalysisRun. Some can delete Topic-wide
outputs and their Job records do not provide reliable AnalysisOutput provenance. The frontend no
longer exposes them.

## Compatibility and Removal Plan

### v0.4.0-dev

- Preserve response bodies, status codes, tables, and historical rows.
- Mark legacy executor operations deprecated in OpenAPI.
- Remove the legacy executor UI and unused frontend clients.
- Route Topic AnalysisRun creation and pipeline=v2 compatibility through one default Work.
- Do not synthesize AnalysisRun rows from Job rows and do not rewrite run_id=NULL outputs.

### Later v0.4.x hardening

- Add targeted deletion at the run lifecycle if product requirements need it.
- Audit retrieval behavior when current and historical output rows coexist.
- Keep compatibility reads until an explicit removal task includes data export/cleanup guidance.

### Future removal

Removing Job/JobItem tables, legacy mutation routes, or historical outputs requires explicit user
scope and a migration plan. No Sunset date is declared in v0.4.

## Invariants

- A new frontend analysis action creates an AnalysisRun, never a Job.
- A Topic has at most one pending/running AnalysisRun and one registered executor in the supported single-process runtime.
- A Work-scoped run selects chunks from exactly one Document.
- Topic creation selects the deterministic default Work only.
- Canonical final outputs carry run_id; job_id is not used as an AnalysisRun bridge.
- Compatibility code never deletes or migrates historical data merely because it is deprecated.