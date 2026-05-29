# LongNovelInsight v0.3.0-dev — Data Model

All models are SQLModel classes backed by SQLite. v0.2 added hybrid storage for large analysis artifacts; v0.3 adds source locator fields, retrieval tracing, and FTS5 full-text search.

> **Storage note:** v0.2 added disk-based artifact storage for large analysis JSON (>64KB). v0.3 adds FTS5 virtual tables (not managed by SQLModel) and source locator metadata.

## Entity-Relationship Summary

```
ModelProvider  ?──*  Topic
Topic          1──1  TopicProviderConfig
Topic          1──1  Document
Document       1──*  Chapter
Chapter        1──*  Chunk
Topic          1──*  AnalysisOutput
Topic          1──*  ChatSession
ChatSession    1──*  ChatMessage
Topic          1──*  Job
Job            1──*  JobItem
Topic          1──*  RetrievalTrace
ChatSession    1──*  RetrievalTrace  (optional, nullable)
Chunk          -──-  chunk_fts        (FTS5 virtual table, no FK)
```

## Enums (backend/models/enums.py)

| Enum | Values |
|------|--------|
| `AnalysisType` | `overview`, `characters`, `relations`, `events`, `causality`, `themes` |
| `JobType` | `parse`, `analysis` |
| `JobStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled`, `partial_success` (v0.2 AnalysisRun) |
| `JobItemStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| `AnalysisMode` (v0.2) | `preview`, `range`, `full`, `incremental` |
| `AtomType` (v0.2) | `character`, `event`, `relation`, `causal_link`, `theme_signal`, `worldbuilding`, `foreshadowing`, `open_question` |
| `DocumentStatus` | `uploaded`, `parsing`, `parsed`, `failed` |
| `TopicStatus` | `created`, `uploaded`, `parsed`, `analyzing`, `ready`, `failed` |

All enum values are lowercase strings (Python `StrEnum`).

## Models

### Topic (`topic`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique topic ID |
| `name` | str | User-given name |
| `description` | str | optional | Notes |
| `provider_id` | FK → model_provider | optional, nullable | Bound LLM provider. Nullable at creation; required before analysis/chat. |
| `storage_bytes` | int | Disk usage in bytes |
| `status` | str | TopicStatus enum value |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### ModelProvider (`model_provider`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique provider ID |
| `name` | str (unique) | Display name |
| `provider_type` | str | Always `openai_compatible` in v0.1.0 |
| `base_url` | str | API base URL |
| `api_key` | str | User's API key (never returned in API responses) |
| `model_name` | str | Model identifier |
| `context_window` | int | Context window size (default 1_000_000) |
| `max_output_tokens` | int | Max output tokens (default 8192) |
| `temperature` | float | Sampling temperature (default 0.2) |
| `is_default` | bool | Whether this is the default provider |
| `masked_api_key` | (property) | Computed masked version of api_key |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### TopicProviderConfig (`topic_provider_config`)

Per-Topic provider configuration overrides. Does NOT mutate the global Provider.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique config ID |
| `topic_id` | FK → topic (unique) | Owning topic (one-to-one) |
| `provider_id` | FK → model_provider | optional | Bound provider for this topic |
| `base_url_override` | str | optional | Override base URL |
| `model_name_override` | str | optional | Override model name |
| `context_window_override` | int | optional | Override context window |
| `max_output_tokens_override` | int | optional | Override max output tokens |
| `temperature_override` | float | optional | Override temperature (0–2) |
| `thinking_mode_override` | str | optional | "enabled" / "disabled" / "provider_default" |
| `reasoning_effort_override` | str | optional | "high" / "max" |
| `analysis_parallelism_override` | int | optional | Override parallelism (1–6) |
| `recommended_profile` | str | optional | Applied recommendation profile name |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### Document (`document`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique document ID (independent of topic_id) |
| `topic_id` | FK → topic (unique) | Owning topic (one-to-one in v0.1.0) |
| `original_filename` | str | Original uploaded filename |
| `stored_filename` | str | `original.txt` or `original.epub` |
| `file_type` | str | `txt` or `epub` |
| `content_type` | str | optional | MIME type from upload |
| `encoding` | str | Source encoding; `"epub"` for EPUB documents |
| `file_size_bytes` | int | Original uploaded file size |
| `char_count` | int | Character count after decoding |
| `storage_path` | str | Relative path within `data/` |
| `metadata_json` | str | optional | v0.3: EPUB metadata (title, creator, language, etc.) |
| `status` | str | DocumentStatus enum value |
| `created_at` | datetime | Upload timestamp |
| `updated_at` | datetime | Last update timestamp |

### Chapter (`chapter`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique chapter ID |
| `topic_id` | FK → topic | Owning topic |
| `document_id` | FK → document | Owning document |
| `chapter_index` | int | Chapter number (0-based) |
| `title` | str | Detected chapter title |
| `start_char` | int | Character offset where chapter starts |
| `end_char` | int | Character offset where chapter ends |
| `char_count` | int | Character count |
| `source_href` | str | optional | v0.3: EPUB XHTML href or `txt://original` |
| `nav_order` | int | optional | v0.3: EPUB spine/toc order |
| `metadata_json` | str | optional | v0.3: Chapter-level metadata |
| `created_at` | datetime | Creation timestamp |

### Chunk (`chunk`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique chunk ID |
| `topic_id` | FK → topic | Owning topic |
| `document_id` | FK → document | Owning document |
| `chapter_id` | FK → chapter | optional | Owning chapter |
| `chunk_index` | int | Chunk number (0-based within topic) |
| `chapter_index` | int | optional | Chapter number (for ordering) |
| `text` | str | Full chunk text (stored in SQLite in v0.1) |
| `start_char` | int | Character offset within document |
| `end_char` | int | Character offset within document |
| `char_count` | int | Character count |
| `estimated_tokens` | int | Estimated token count (chars / 1.5 for Chinese) |
| `source_locator_json` | str | optional | v0.3: Source locator (href, chapter index, offsets) |
| `created_at` | datetime | Creation timestamp |

### RetrievalTrace (`retrieval_trace`)

v0.3: Stores retrieval debug records for search/chat/retrieve calls.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique trace ID |
| `topic_id` | FK → topic | Owning topic |
| `session_id` | FK → chat_session | optional | Chat session if from chat |
| `message_id` | FK → chat_message | optional | Message if from chat |
| `query` | str | Original query string |
| `method` | str | Retrieval method: `fts`, `keyword_fallback`, `structured`, `hybrid`, etc. |
| `results_json` | str | JSON array of ranked candidates (chunk IDs, scores, snippets) |
| `created_at` | datetime | Timestamp |

### chunk_fts (FTS5 Virtual Table)

v0.3: SQLite FTS5 virtual table for full-text search over chunk text/titles. Not a SQLModel table — created via raw SQL `CREATE VIRTUAL TABLE`.

| Column | Content |
| ------ | ------- |
| `chunk_id` | UNINDEXED |
| `topic_id` | UNINDEXED |
| `document_id` | UNINDEXED |
| `chapter_index` | UNINDEXED |
| `chunk_index` | UNINDEXED |
| `title` | Indexed content |
| `text` | Indexed content |

### EmbeddingCache (`embedding_cache`)

v0.3 Step 10: Optional cache for JSON embedding vectors (SQLite, small-scale only, no ANN index). Table is created unconditionally but only populated when `ENABLE_SEMANTIC_RERANK` is enabled and a real embedding provider is configured.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique cache entry ID |
| `topic_id` | FK → topic | Owning topic |
| `source_type` | str | `chunk`, `analysis_output`, or `atom` |
| `source_id` | str | Chunk/output/atom ID |
| `model_name` | str | Embedding model name |
| `vector_json` | str | JSON array of float values |
| `created_at` | datetime | Creation timestamp |

### AnalysisOutput (`analysis_output`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique analysis ID |
| `topic_id` | FK → topic | Owning topic |
| `job_id` | FK → job | optional | Associated job |
| `output_type` | str | AnalysisType enum value |
| `title` | str | Human-readable title |
| `content_json` | str | Full LLM response as JSON string (stored in SQLite in v0.1) |
| `source_chunk_ids` | str | JSON array of source chunk IDs |
| `evidence_quotes` | str | JSON array of direct quotes |
| `confidence` | float | Overall confidence score (0.0–1.0) |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### ChatSession (`chat_session`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique session ID |
| `topic_id` | FK → topic | Owning topic |
| `title` | str | User-given or auto-generated title |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### ChatMessage (`chat_message`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique message ID |
| `session_id` | FK → chat_session | Owning session |
| `role` | str | `user`, `assistant`, or `system` |
| `content` | str | Message text |
| `evidence_json` | str | optional | JSON evidence list (assistant messages) |
| `uncertainty` | str | optional | Uncertainty notes (assistant messages) |
| `prompt_tokens` | int | Prompt tokens used (from LLM response) |
| `completion_tokens` | int | Completion tokens used (from LLM response) |
| `total_tokens` | int | Total tokens used (from LLM response) |
| `model_used` | str | optional | Actual model that generated the response |
| `created_at` | datetime | Message timestamp |

### Job (`job`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique job ID |
| `topic_id` | FK → topic | Owning topic |
| `job_type` | str | JobType enum value: `parse` or `analysis` |
| `status` | str | JobStatus enum value |
| `progress_current` | int | Items completed |
| `progress_total` | int | Total items |
| `message` | str | optional | Human-readable status |
| `error_message` | str | optional | Error details if failed |
| `started_at` | datetime | optional | When job started |
| `finished_at` | datetime | optional | When job finished |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### JobItem (`job_item`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique item ID |
| `job_id` | FK → job | Owning job |
| `item_type` | str | AnalysisType enum value |
| `status` | str | JobItemStatus enum value |
| `progress_current` | int | 0 |
| `progress_total` | int | 1 |
| `message` | str | optional | Status message |
| `error_message` | str | optional | Error details |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

## Deletion Cascades

| Delete Target | Cascades To |
| ------------- | ----------- |
| ModelProvider | Blocked if referenced by any Topic |
| Topic | Document, Chapter, Chunk, AnalysisOutput, ChatSession → ChatMessage, Job → JobItem |
| ChatSession | ChatMessage |
| Document | Chapter → Chunk |

All cascade-deleted records also trigger removal of associated files in `data/`.

## v0.2 Backend Additions — Schema Foundation

### AnalysisRun (`analysis_run`)

One row per v2 analysis run. Represents the full staged pipeline: extraction → merge → final output.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique run ID |
| `topic_id` | FK → topic | Owning topic |
| `job_id` | FK → job | optional | Associated v1 job, if any |
| `mode` | str | AnalysisMode: preview / range / full / incremental |
| `status` | str | Reuses JobStatus (pending / running / succeeded / failed / cancelled / partial_success) |
| `requested_types_json` | str | JSON array of requested output types |
| `chunk_selection_json` | str | JSON object describing chunk selection params |
| `effective_config_json` | str | JSON object of resolved effective provider config |
| `progress_current` | int | Total items completed |
| `progress_total` | int | Total items |
| `extraction_total/succeeded/failed` | int | Extraction stage counters |
| `merge_total/succeeded/failed` | int | Merge stage counters |
| `prompt_tokens` | int | Total prompt tokens used |
| `completion_tokens` | int | Total completion tokens used |
| `total_tokens` | int | Total tokens used |
| `model_used` | str | optional | Actual model used |
| `error_message` | str | optional | Error details if failed |
| `metadata_json` | str | Stage timings, warnings, failed items |
| `started_at / finished_at` | datetime | optional | Run timing |
| `created_at / updated_at` | datetime | Timestamps |

### LocalExtraction (`local_extraction`)

One row per chunk per run. Stores the LLM's raw local_extraction JSON output.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique extraction ID |
| `run_id` | FK → analysis_run | Owning run |
| `topic_id` | FK → topic | Owning topic |
| `chunk_id` | FK → chunk | Source chunk |
| `status` | str | pending / running / succeeded / failed |
| `attempt_count` | int | Number of extraction attempts |
| `content_json` | str | optional | Raw LLM response JSON |
| `source_chunk_ids` | str | JSON array of source chunk IDs |
| `evidence_quotes` | str | JSON array of evidence quotes |
| `confidence` | float | Overall confidence (0.0–1.0) |
| `prompt_tokens / completion_tokens / total_tokens` | int | Token usage |
| `model_used` | str | optional | Model that produced the extraction |
| `error_message` | str | optional | Error details if failed |
| `started_at / finished_at` | datetime | optional | Timing |
| `created_at / updated_at` | datetime | Timestamps |

### ExtractedAtom (`extracted_atom`)

Normalized atomic facts produced from local extraction results.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique atom ID |
| `run_id` | FK → analysis_run | Owning run |
| `topic_id` | FK → topic | Owning topic |
| `local_extraction_id` | FK → local_extraction | optional | Source extraction |
| `chunk_id` | FK → chunk | optional | Source chunk |
| `atom_type` | str | AtomType: character / event / relation / causal_link / theme_signal / worldbuilding / foreshadowing / open_question |
| `stable_id` | str | Canonical stable ID (not LLM-generated) |
| `canonical_name` | str | optional | Canonical entity name |
| `title` | str | optional | Human-readable title |
| `summary` | str | optional | Brief description |
| `content_json` | str | JSON with full atom details |
| `source_chunk_ids` | str | JSON array |
| `evidence_quotes` | str | JSON array |
| `confidence` | float | 0.0–1.0 |
| `chapter_index / chunk_index` | int | optional | Source position |
| `order_index` | int | optional | Ordering hint |
| `created_at / updated_at` | datetime | Timestamps |

### AnalysisOutput (`analysis_output`) — v0.2 Changes

| Field | Type | Description |
| ----- | ---- | ----------- |
| `run_id` | FK → analysis_run | optional, nullable | Links output to v2 AnalysisRun. NULL for v1 outputs. |

v0.2 merge stage writes intermediate AnalysisOutput rows with these `output_type` values:
`merge_overview`, `merge_characters`, `merge_events`, `merge_relations`, `merge_causality`, `merge_themes`, `merge_worldbuilding`, `merge_foreshadowing`.

The 6 core types (overview, characters, relations, events, causality, themes) have final output builders that produce frontend-compatible AnalysisOutput rows. Worldbuilding and foreshadowing have merge support but no final output builders yet. Timeline and character_arcs are planned but not yet implemented.
