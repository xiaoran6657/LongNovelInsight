# Next Actions

Statuses: `ready`, `in_progress`, `blocked`, `review`, `done`.

`ready` identifies a scoped v0.4.x candidate that can be selected by the user. It does not by
itself authorize implementation, dependency changes, or Git publication.

## Current Post-Release Remediation

| ID | Status | Area | Task |
| --- | --- | --- | --- |
| CROSS-001 | done | backend | Preserve valid entity references across retained graph scopes and repair pre-patch snapshots on startup |
| RUN-003 | done | backend | Resolve AnalysisRun chapter titles from the selected chunks in initial, retry, and resume paths |
| STORAGE-001 | done | backend | Maintain and startup-backfill Topic.storage_bytes as the aggregate of all Work source Documents |
| STATUS-001 | done | docs | Refresh post-release branch state, archive the v0.4.0 completion queue, and create a v0.4.x queue |

The current remediation is implemented and fully backend-verified in the working tree. It remains
uncommitted and unpublished pending explicit Git authorization.

## Ready v0.4.x Maintenance Queue

| ID | Status | Area | Task | Acceptance Boundary |
| --- | --- | --- | --- | --- |
| CHAT-003 | ready | frontend/backend | Add Work-scoped chat evidence filtering | Chat retrieval and citations remain inside the selected Work without changing Topic/session ownership |
| USAGE-001 | ready | backend | Complete retry attempt-history usage merging | Retry metadata retains deterministic per-attempt token and cost-estimate history without real provider calls in tests |
| GRAPH-001 | ready | frontend | Add an interactive relationship graph projection | Use the existing graph endpoint and current frontend stack; preserve table/evidence access and add no visualization dependency without approval |
| TIMELINE-001 | ready | frontend/backend | Add timeline pagination and evidence expansion | Pagination totals and Work filters stay exact; evidence remains source-linked |
| A11Y-001 | ready | frontend | Run a narrow-window responsive and keyboard accessibility pass | Core Work, analysis, chat, graph, and timeline flows remain usable at narrow widths and by keyboard |

## Scope Guard

Completed v0.4.0 delivery details are archived in
[`archive/v0.4.0_COMPLETED.md`](archive/v0.4.0_COMPLETED.md). Roadmap items beyond v0.4 require an
explicit user scope change before implementation.
