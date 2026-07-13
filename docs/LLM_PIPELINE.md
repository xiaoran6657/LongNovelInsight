# LongNovelInsight v0.4.0 — LLM Pipeline

This document describes the current LLM call boundaries and the authoritative analysis and chat
pipelines. Endpoint request and response shapes live in [API.md](API.md); AnalysisRun lifecycle and
legacy deprecation rules live in [ANALYSIS_RUN_CONTRACT.md](ANALYSIS_RUN_CONTRACT.md).

## External Call Boundary

LongNovelInsight sends requests directly to the user-selected OpenAI-compatible chat completions
endpoint. There is no LLM framework, remote LongNovelInsight service, or background cloud worker.
The configured API key is stored in the local SQLite database, omitted from API responses, and sent
only in the `Authorization` header to the selected provider.

All chat-completions HTTP requests use
`backend/services/llm_client.py::OpenAICompatibleLLMClient`. The wrapper:

- posts to `{base_url}/chat/completions`;
- supports JSON response mode and provider-specific request fields;
- returns content, model, usage, and `finish_reason`;
- masks no data by itself, so each calling service must sanitize provider errors before persistence
  or logging;
- may retry transport failures and an invalid HTTP response envelope when `max_retries` is greater
  than zero, but does not retry non-200 HTTP status codes.

Product code makes a real LLM request only at these visible boundaries:

| User action | Runtime caller | LLM behavior |
| --- | --- | --- |
| Start, retry, or resume an AnalysisRun | `local_extraction_worker.py` | One request per chunk scheduled by that operation and attempt |
| Send a grounded chat message | `chat_service.py` | One request when retrieval finds evidence |
| Edit and resend the latest chat turn | `chat_service.py` | One request when retrieval finds evidence; replacement is committed only after generation succeeds |
| Test a provider | `provider_test_service.py` | One minimal request with `max_tokens=8` |

Startup recovery, parsing, search/retrieval, merge, final-output generation, and cross-Work
materialization never call an LLM. Default tests replace the LLM boundary and must not make external
requests.

## Provider Resolution

Authoritative analysis resolves effective settings through
`provider_config_service.get_effective_config()`:

```text
TopicProviderConfig override > ModelProvider value > Provider preset default
```

The resolved model, base URL, temperature, maximum output tokens, thinking mode, and analysis
parallelism are copied into `AnalysisRun.effective_config_json` when the run is created. The API key
is not copied into the run; execution resolves it from the selected Provider.

Chat currently selects `Topic.provider_id`, falling back to the default Provider. Provider Test uses
the selected `ModelProvider` row directly. These call sites therefore do not share the full analysis
override resolution path.

For local extraction, thinking mode is sent as
`{"thinking": {"type": "enabled|disabled"}}`. Structured extraction recommends disabled thinking
because reasoning tokens increase latency and output-size risk.

## Authoritative AnalysisRun Pipeline

New product code uses `AnalysisRun` and the `analysis_run_service` lifecycle facade as the only
authoritative analysis lifecycle. Initial execution is implemented in
`analysis_run_execution_service.py`; retry and resume are implemented in
`analysis_run_continuation_service.py`. The explicit entry point is:

```http
POST /api/works/{work_id}/analysis/runs
```

`POST /api/topics/{topic_id}/analysis/runs` is a compatibility facade that resolves the Topic's
deterministic default Work and invokes the same service. It never creates a cross-Work run.

### 1. Select and persist the scope

The backend resolves one Work and its single Document, then selects chunks in one of four modes:

- `preview`: the requested or recommended leading subset;
- `range`: a chunk-index or chapter-index range;
- `full`: all chunks in the selected Document;
- `incremental`: chunks not successfully extracted by the selected prior-run baseline.

The exact ordered `selected_chunk_ids` and `work_id` are persisted in
`AnalysisRun.chunk_selection_json`. Execution reads these persisted IDs rather than re-running the
selection query, which keeps retries and resume tied to the original scope. Requested analysis
types and the effective provider configuration are also persisted before execution starts.

Creating a run with `start_immediately=false` leaves it pending and performs no LLM request.

### 2. Extract once per selected chunk

Initial execution loads the persisted chunks and submits one local-extraction task per chunk to a
`ThreadPoolExecutor`. Parallelism is clamped to 1–6. Worker tasks have no database access; they
return a `LocalExtractionResult`, and the orchestrator writes results using short-lived sessions.

Each request contains:

- the stable system prompt from `backend/prompts/local/local_extraction.md`;
- a user message with chunk ID, chapter/chunk metadata, optional chapter title, and chunk text;
- `response_format={"type": "json_object"}`;
- the resolved model, temperature, maximum output tokens, and thinking setting.

The response parser accepts a JSON object directly and can recover an object from a code fence or
surrounding text. Validation requires `analysis_type="local_extraction"`, the expected `chunk_id`,
and dictionary atom items. Missing per-item `source_chunk_ids` or `evidence_quotes` are reported as
warnings rather than hard validation failures.

Successful parsed data is serialized as canonical JSON in `LocalExtraction.content_json`. The
normalizer then creates deterministic `ExtractedAtom` rows for characters, events, relations,
causal links, theme signals, worldbuilding, foreshadowing, and open questions. Malformed individual
atoms are skipped with warnings instead of invalidating other atoms from the chunk.

### 3. Adaptive extraction retry

The authoritative worker disables retries in the generic HTTP client and owns its retry policy.
There is one initial attempt and at most two worker retries.

Retryable conditions are:

- HTTP 429, 500, 502, 503, or 504;
- transport, network, timeout, rate-limit, or equivalent transient errors;
- content JSON parse failures, including likely truncation.

Non-retryable provider and validation errors stop that chunk immediately. Backoff is longest for
429 responses (15 then 30 seconds), shorter for JSON/truncation failures (1.5 then 3 seconds), and
3 then 6 seconds for other retryable transport failures.

For JSON failures, the completion budget escalates from the configured value to
`min(configured * 2, 16384)`, then to 16384. A response is treated as likely truncated when
`finish_reason == "length"` or completion usage is within eight tokens of the current budget.

### 4. Account for every observable attempt

Each `LocalExtraction` stores cumulative prompt, completion, total, reasoning, prompt-cache-hit,
and prompt-cache-miss tokens. `attempt_usage_json` records per-attempt status, token budget, usage,
finish reason, and sanitized error for the latest worker invocation; retry/resume preserves earlier
token totals but does not yet merge every historical attempt record. `usage_unavailable_attempts`
counts attempts for which the provider returned no usage data.

Run totals are derived from the extraction rows. Merge and final stages record zero LLM usage. A
provider may still bill an attempt whose failure response did not include usage, so local totals
can be lower than the provider dashboard; `usage_unavailable_attempts` makes that limitation
visible.

`POST /api/works/{work_id}/analysis/estimate` applies the same chunk selection and effective
configuration without making an LLM call. It reports one expected LLM request per selected chunk
before retries and estimates extraction tokens using prompt overhead, an expected output fraction,
thinking-mode inflation, and a mode-specific retry buffer. It reports merge and final LLM cost as
zero.

### 5. Deterministic merge

When at least one extraction succeeds, `merge_service.py` groups and consolidates `ExtractedAtom`
rows in Python. No merge prompt is sent to a provider. Merge supports:

- overview;
- characters;
- relations;
- events;
- causality;
- themes;
- worldbuilding;
- foreshadowing.

The stage writes idempotent `AnalysisOutput` projections named `merge_<type>`, including source
chunk IDs, evidence quotes, confidence, and stable identifiers. Re-running a merge replaces the
same run/type projection. The markdown files under `backend/prompts/merge/` are retained contract
references and prompt-loader test fixtures; the current merge runtime does not invoke them.

### 6. Deterministic final outputs

`final_output_service.py` converts successful merge projections into the six frontend-compatible
output families: overview, characters, relations, events, causality, and themes. This stage is also
Python-only and idempotent. Worldbuilding and foreshadowing have merge support but no final-output
builders in v0.4.

Final `AnalysisOutput` rows carry a non-null `run_id`, which is authoritative provenance. Small JSON
payloads remain inline; payloads larger than 64 KiB may be stored under the Topic artifact directory
with an `AnalysisArtifact` pointer. Historical outputs with `run_id=null` remain readable but are
not created by the authoritative path.

### 7. Complete, cancel, retry, and resume

Run status becomes:

- `succeeded` when all extractions and requested merge/final stages succeed;
- `partial_success` when usable results exist but an extraction or later stage failed;
- `failed` when no extraction succeeds or an unhandled failure prevents completion;
- `cancelled` after an explicit cancellation request.

Cancellation prevents subsequent results from being saved when observed and skips merge/final.
In-flight provider calls cannot be forcibly terminated.

`retry-failed` reprocesses failed extraction rows, replaces their atoms, then reruns merge and final.
`resume` never reruns succeeded chunks; it processes missing rows and, by default, failed rows,
then reruns deterministic stages. Usage is recomputed from all extraction rows after continuation.

A process-local registry permits at most one executor per Topic and prevents duplicate execution of
the same run in the supported single-process backend. On startup, orphaned `running` rows are marked
failed with recovery metadata and remain explicitly resumable. Pending rows are left unchanged, and
startup recovery never triggers an LLM call. Multiple backend processes sharing one SQLite database
are outside the v0.4 runtime contract.

## Evidence-Grounded Chat

Chat is a separate LLM pipeline and does not create AnalysisRuns.

1. The service persists the user message with a logical `turn_id` and session-local
   `sequence_index`.
2. `hybrid_retrieve()` gathers FTS5, CJK keyword fallback, structured atom, and AnalysisOutput
   candidates. Optional `work_ids` filter the annotated candidates.
3. If hybrid retrieval returns no candidates, the service tries the legacy fuzzy chunk/output
   scorer. Stored scores are ranking signals and consumers must treat their scale as
   method-dependent.
4. A `RetrievalTrace` is persisted for every attempt, including empty retrieval and LLM failure.
5. If no evidence exists, the service skips the LLM and stores a conservative assistant response.
6. Otherwise, the provider receives the fixed chat system prompt, up to six recent user/assistant
   messages for reference resolution, and the current evidence plus question. Factual claims must
   remain grounded in the current evidence.
7. The assistant content is parsed as JSON with `answer`, `evidence`, and `uncertainty`. Structured
   evidence stored by the backend comes from retrieval candidates, not untrusted LLM citations.

Assistant messages share the user message's `turn_id` and `sequence_index` and set
`reply_to_message_id` explicitly. Listing, pair deletion, and resend use these fields, with a legacy
fallback only for unbackfilled rows. Ordering is stable even when timestamps tie.

Normal sends keep the user message and retrieval trace when the provider fails and store a guarded
assistant error. Edit/resend generates without a long SQLite transaction, then locks and revalidates
the expected latest pair. It replaces the pair and trace atomically only after successful generation;
a generation failure leaves the original exchange unchanged.

Chat uses the generic client's default two retries for transport failures or an invalid HTTP
response envelope. It does not adapt the token budget or retry malformed JSON inside the assistant
message; malformed content is preserved with an uncertainty marker.

## Provider Test

Provider Test makes one synchronous request using the selected Provider row, a 60-second timeout,
no client retries, temperature 0, and `max_tokens=8`. Any successful chat-completions response marks
the connection successful; the response text is not used as analysis data. Provider errors are
sanitized before they are returned.

## Deprecated Compatibility Pipelines

The v1 synchronous executor, v1 async executor, single-type executor, and Job/JobItem APIs still use
the six prompts in `backend/prompts/{overview,characters,relations,events,causality,themes}.md` and
may make per-type LLM calls. They remain callable only for v0.4 compatibility, are marked deprecated
in OpenAPI, and have no frontend caller. They must not be used for new product work.

The deprecated paths have independent lifecycle, retry, deletion, and provenance behavior. Their
historical `AnalysisOutput` rows may have `run_id=null`. Do not infer authoritative AnalysisRun
semantics from those rows, and do not delete or rewrite them during ordinary v0.4 operation.
