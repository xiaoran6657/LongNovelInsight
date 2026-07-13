# Frontend API Integration Contract — v0.4.0

This document defines how the current React frontend consumes the backend. It intentionally does
not duplicate every request and response schema.

- Runtime OpenAPI at `/docs` or `/openapi.json` is the exact schema authority.
- [API.md](API.md) is the complete human endpoint map.
- [ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md) owns analysis lifecycle and deprecation.
- `frontend/src/api/types.ts` is the frontend compile-time representation, not an independent API
  specification.

## Transport and Errors

`frontend/src/api/client.ts` provides the shared `apiRequest<T>` wrapper.

- Base URL: `VITE_API_BASE_URL`, default `http://127.0.0.1:8000`.
- The wrapper strips trailing slashes from the configured base URL.
- JSON requests set `Content-Type: application/json`; uploads use `FormData` so the browser owns
  the multipart boundary.
- Non-2xx responses become `ApiError(status, detail)`.
- FastAPI `detail` may be a string, validation array, or object; the wrapper normalizes it to a
  displayable string.
- Network failures use status `0`. Aborted requests report `Request aborted`.
- `204`, an explicit zero content length, and an empty body resolve as `undefined`.

The backend permits both Vite development origins: `http://localhost:5173` and
`http://127.0.0.1:5173`.

## Frontend-Owned Endpoint Families

Each module under `frontend/src/api/` owns one domain. New calls must be added to the matching
module and use the shared wrapper.

| Module | Current responsibility |
| --- | --- |
| `health.ts` | Backend health |
| `providers.ts` | Provider CRUD, presets, detection, explicit connection test |
| `topics.ts` | Topic CRUD, provider binding, effective Topic configuration |
| `works.ts` | Work CRUD, Work upload/parse/source reads, estimate, runs, outputs |
| `documents.ts`, `parse.ts` | Topic default-Work compatibility facades |
| `analysis.ts` | Topic facade creation/listing, run detail/control, outputs |
| `search.ts`, `retrieve.ts`, `entities.ts` | Source search, retrieval, evidence, similar scenes |
| `crossWork.ts`, `graphs.ts`, `timeline.ts` | Cross-work derived views and builds |
| `chat.ts` | Session/message CRUD, send, and atomic resend |

The frontend has no client for deprecated Job endpoints or legacy analysis executors.

## Topic and Work Scope

A Topic is a story universe or workspace. A Work is one novel or volume inside it. All new source
and analysis UI must carry an explicit `workId`.

- List/create Works through `/api/topics/{topic_id}/works`.
- Read/update/delete a Work through `/api/works/{work_id}`.
- Upload, parse, chapters, chunks, metadata, estimate, runs, and outputs use `/api/works/{work_id}`.
- A Work has at most one source Document.
- Deleting a non-empty Work returns `409`; the UI must not imply that derived data will be silently
  discarded.
- Topic-level document and parse routes remain default-Work facades for compatibility. New Work UI
  must not use them when an explicit Work is available.

Search and retrieve accept optional Work filters. A frontend filter must send only Work IDs from
the current Topic and must keep the filter in the relevant query key.

## AnalysisRun Flow

New analysis follows one visible, credit-aware sequence:

1. Select one Work and a mode: `preview`, `range`, `full`, or `incremental`.
2. Call `POST /api/works/{work_id}/analysis/estimate` with the same selection body that will be used
   to create the run.
3. Display numeric input/output/total token estimates and provider/model context.
4. Require explicit user confirmation because the next action may spend provider credit.
5. Call `POST /api/works/{work_id}/analysis/runs`.
6. Poll `GET /api/analysis/runs/{run_id}` until a terminal status.
7. Refresh Work run history and Work outputs.

The estimate is read-only: it creates no run and makes no LLM request. It is not a currency quote
and actual usage can differ because model output and retries vary.

The Topic Overview may use `POST /api/topics/{topic_id}/analysis/runs`; that route resolves one
deterministic default Work and enters the same lifecycle. It must never be used to imply a
multi-Work combined analysis.

### Status and control

AnalysisRun statuses are lowercase strings: `pending`, `running`, `succeeded`, `failed`,
`cancelled`, or `partial_success`.

- Cancel: `POST /api/analysis/runs/{run_id}/cancel`.
- Retry failed chunks: `POST /api/analysis/runs/{run_id}/retry-failed`.
- Resume an interrupted run: `POST /api/analysis/runs/{run_id}/resume?retry_failed=true|false`.

Control responses acknowledge background work; the UI must use subsequent run detail, not mutable
human message text, as the state authority. Backend restart can convert an orphaned `running` row
to `failed` with recovery metadata. It never resumes automatically.

### Outputs

Current final outputs have non-null `run_id`. Work output reads omit internal `merge_*` rows and
exclude historical Topic-wide outputs. Topic output reads may contain both current and historical
rows, so rendering must tolerate `run_id = null`.

`content_json` is untrusted persisted JSON. The UI must continue to:

- parse object or serialized-object content;
- filter malformed nested collections;
- isolate an unexpected output card failure so sibling cards remain usable;
- avoid assuming every requested atom family has a final UI projection.

## Cross-Work Scope

Cross-work build and GET filters follow one shared rule: an omitted or empty `work_ids` list means
the canonical All scope.

- Normalize selected Work IDs by sorting and deduplicating them.
- Reject or clear selections when the active Topic changes.
- Entity registry data is canonical Topic-wide even when a run request carries a scope.
- Graph snapshots are stored per normalized scope. Unfiltered graph GET reads only All; a filtered
  GET may read a compatible scoped snapshot with All fallback.
- Timeline writes are Work-partitioned. A scoped rebuild replaces only the selected Works.
- A foreign-Topic Work filter returns `404`; it is not an empty result.

The frontend must label All versus selected Works explicitly and include the normalized filter in
query keys. A scoped refresh must not invalidate or overwrite unrelated scoped cache entries by
accident.

## Chat Contract

Chat is Topic-scoped and evidence-grounded.

- Create/list sessions under `/api/topics/{topic_id}/chat/sessions`.
- List/send messages under `/api/chat/sessions/{session_id}/messages`.
- Edit and regenerate a pair with
  `POST /api/chat/sessions/{session_id}/messages/{user_message_id}/resend`.
- Delete a session or message only through the server-owned delete routes.

Each new user/assistant pair has explicit linkage:

| Field | Meaning |
| --- | --- |
| `turn_id` | Shared logical exchange identifier |
| `sequence_index` | Stable session-local turn order, shared by the pair |
| `reply_to_message_id` | Assistant link to its user message |

New UI logic must pair messages by these fields, not by timestamp adjacency. Nullable linkage must
remain supported for historical rows.

`evidence_json` may be a structured object/list, a legacy string array, malformed JSON, or null.
The renderer must normalize each item before use. Evidence scores are method-dependent ranking
values, not probabilities and not guaranteed to be in `[0, 1]`.

Atomic resend sends:

```json
{
  "content": "edited user question",
  "expected_assistant_message_id": "message-id",
  "work_ids": ["optional-work-id"]
}
```

The expected assistant ID protects against replacing a stale pair. A conflict must trigger a
message refresh rather than optimistic overwrite. The backend performs retrieval/LLM generation
before its short atomic replacement transaction; the old pair remains intact if generation fails.

## TanStack Query Keys and Mutations

`frontend/src/queryKeys.ts` is the shared key factory. Do not recreate equivalent array literals in
Topic Detail or Chat.

Rules:

- Include every server-selection input that changes a response, including Topic/Work/session IDs,
  Work filters, pagination, and `includeText`.
- Use factory prefixes for family invalidation, such as all chunk views for one Topic.
- On a successful mutation, update exact cached data only when the response is authoritative;
  otherwise invalidate the narrow affected family.
- Do not let optimistic Chat updates invent durable linkage. Reconcile with the server response.
- Clear active Work/session UI state when its owning Topic or session is deleted.

## Compatibility and Deprecated Routes

The following APIs remain backend-compatible in v0.4 but must not gain new frontend callers:

- `POST /api/topics/{topic_id}/analysis/run` and its `pipeline=v2` bridge.
- `POST /api/topics/{topic_id}/analysis/run-async`.
- `POST /api/topics/{topic_id}/analysis/run/{output_type}`.
- `/api/topics/{topic_id}/analysis/jobs`, `/analysis/status`, and
  `/api/analysis/jobs/{job_id}` operations.

Historical output rows, legacy evidence arrays, and nullable Chat linkage remain readable. Backend
compatibility is not permission to expose a second execution UX.

## Verification Boundary

- Pure formatting, selection, query-key, and normalization logic belongs in fast unit tests.
- API workflow changes require Playwright coverage with mocked external APIs where practical.
- Backend-integrated upload/parse/AnalysisRun smoke uses temporary database/data paths and mocks
  only the LLM extraction boundary.
- Default tests must never call a real provider or mutate the real `data/` directory.
