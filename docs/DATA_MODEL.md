# LongNovelInsight v0.1.0 — Data Model

All models are SQLModel classes backed by SQLite. In v0.1.0, all data including chunk text and analysis JSON is stored in SQLite for simplicity.

> **Storage note:** v0.1 stores chunk text and analysis JSON in SQLite columns (`Chunk.text`, `AnalysisOutput.content_json`). Future versions may migrate large text to `data/chunks/*.txt` and `data/analyses/*.json`.

## Entity-Relationship Summary

```
ModelProvider  ?──*  Topic
Topic          1──1  Document
Document       1──*  Chapter
Chapter        1──*  Chunk
Topic          1──*  AnalysisOutput
Topic          1──*  ChatSession
ChatSession    1──*  ChatMessage
Topic          1──*  Job
Job            1──*  JobItem
```

## Enums (backend/models/enums.py)

| Enum | Values |
|------|--------|
| `AnalysisType` | `overview`, `characters`, `relations`, `events`, `causality`, `themes` |
| `JobType` | `parse`, `analysis` |
| `JobStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
| `JobItemStatus` | `pending`, `running`, `succeeded`, `failed`, `cancelled` |
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

### Document (`document`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique document ID (independent of topic_id) |
| `topic_id` | FK → topic (unique) | Owning topic (one-to-one in v0.1.0) |
| `original_filename` | str | Original uploaded filename |
| `stored_filename` | str | Always `original.txt` |
| `file_type` | str | Always `txt` in v0.1.0 |
| `content_type` | str | optional | MIME type from upload |
| `encoding` | str | Source encoding used for decoding |
| `file_size_bytes` | int | Original uploaded file size |
| `char_count` | int | Character count after decoding |
| `storage_path` | str | Relative path within `data/` |
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
