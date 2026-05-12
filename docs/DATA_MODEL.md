# LongNovelInsight v0.1.0 — Data Model

All models are SQLModel classes backed by SQLite. Large text content (novel body, chunk text, analysis JSON) is stored on disk; SQLite stores metadata and file paths.

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
```

## Models

### ModelProvider

Stores LLM provider configuration. User-configured, not per-Topic.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique provider ID |
| `name` | str (unique) | Display name, e.g. "My DeepSeek" |
| `base_url` | str | API base URL, e.g. `https://api.deepseek.com` |
| `api_key` | str | User's API key (encrypted or plaintext on local disk) |
| `model_name` | str | Model identifier, e.g. `deepseek-chat` |
| `temperature` | float | Default 0.3 for analysis, 0.7 for chat |
| `is_default` | bool | Whether this is the default provider |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### Topic

A workspace grouping one novel, its analysis, and chat history.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique topic ID |
| `name` | str | User-given name, e.g. "Three Kingdoms Analysis" |
| `description` | str (optional) | Optional notes |
| `provider_id` | FK → ModelProvider (optional, nullable) | Bound LLM provider. Nullable at creation; required before analysis/chat. |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### Document

Represents one uploaded novel file. One-to-one with Topic in v0.1.0.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique document ID (independent of topic_id) |
| `topic_id` | FK → Topic (unique) | Owning topic (one-to-one) |
| `original_filename` | str | Original uploaded filename |
| `stored_filename` | str | Stored filename, always "original.txt" |
| `file_type` | str | Always "txt" in v0.1.0 |
| `content_type` | str (optional) | MIME type from upload |
| `encoding` | str | Source encoding used for decoding (utf-8, utf-8-sig, gbk, gb18030, etc.). File is always saved as UTF-8. |
| `file_size_bytes` | int | Original uploaded file size in bytes |
| `char_count` | int | Character count after decoding |
| `storage_path` | str | Relative path within `data/` |
| `status` | str | `uploaded` / `parsed` |
| `created_at` | datetime | Upload timestamp |
| `updated_at` | datetime | Last update timestamp |

### Chapter

A detected chapter boundary within a document.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique chapter ID |
| `document_id` | FK → Document | Owning document |
| `index` | int | Chapter number (0-based) |
| `title` | str | Detected chapter title, e.g. "第一章 宴桃园豪杰三结义" |
| `start_char` | int | Character offset where chapter starts in document text |
| `end_char` | int | Character offset where chapter ends |
| `token_count` | int | Token count for this chapter |
| `word_count` | int | Word count for this chapter |

### Chunk

A fixed-size sliding window of text within a chapter, used as LLM context unit.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique chunk ID |
| `chapter_id` | FK → Chapter | Owning chapter |
| `index` | int | Chunk number within chapter (0-based) |
| `file_path` | str | Path to chunk text in `data/chunks/{chunk_id}.txt` |
| `start_char` | int | Character offset within chapter |
| `end_char` | int | Character offset within chapter |
| `token_count` | int | Token count for this chunk |
| `word_count` | int | Word count for this chunk |

### AnalysisOutput

One analysis result. A Topic has multiple analysis outputs (one per type).

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique analysis ID |
| `topic_id` | FK → Topic | Owning topic |
| `analysis_type` | str | One of: `overview`, `characters`, `relationships`, `events`, `causal_chain`, `themes` |
| `status` | str | `pending` / `running` / `done` / `failed` |
| `file_path` | str | Path to output JSON in `data/analyses/{id}.json` |
| `error_message` | str (optional) | Error details if failed |
| `job_id` | FK → Job (optional) | Associated background job |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

**Output JSON Structure** (stored on disk at `file_path`):

```json
{
  "analysis_type": "characters",
  "results": [
    {
      "name": "刘备",
      "description": "...",
      "traits": ["仁德", "坚忍"],
      "source_chunk_ids": ["uuid1", "uuid2"],
      "evidence_quotes": ["原文引文1", "原文引文2"],
      "confidence": 0.9
    }
  ],
  "model": "deepseek-chat",
  "tokens_used": 4500,
  "generated_at": "2026-05-10T12:00:00Z"
}
```

### ChatSession

A named conversation thread within a Topic.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique session ID |
| `topic_id` | FK → Topic | Owning topic |
| `name` | str | Auto-generated or user-given name |
| `created_at` | datetime | Creation timestamp |

### ChatMessage

A single message in a chat session.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique message ID |
| `session_id` | FK → ChatSession | Owning session |
| `role` | str | `user` or `assistant` |
| `content` | str | Message text (Markdown for assistant) |
| `referenced_chunk_ids` | JSON (list of UUIDs) | Chunks referenced in assistant response |
| `referenced_analysis_ids` | JSON (list of UUIDs) | Analysis outputs referenced |
| `tokens_used` | int | Tokens consumed by this message (prompt + completion) |
| `created_at` | datetime | Message timestamp |

### Job

Tracks long-running background operations.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | UUID (PK) | Unique job ID |
| `topic_id` | FK → Topic | Owning topic |
| `job_type` | str | `parse` or `analysis` |
| `status` | str | `pending` / `running` / `done` / `failed` |
| `progress` | float | 0.0 to 1.0 |
| `progress_message` | str | Human-readable status, e.g. "Splitting chapters..." |
| `error_message` | str (optional) | Error details if failed |
| `result_summary` | JSON (optional) | Summary of results (e.g., "{chapters: 120, chunks: 480}") |
| `created_at` | datetime | Job creation |
| `started_at` | datetime (optional) | When job started |
| `completed_at` | datetime (optional) | When job finished |

## Deletion Cascades

| Delete Target | Cascades To |
| ------------- | ----------- |
| ModelProvider | Blocked if referenced by any Topic |
| Topic | Document, Chapter, Chunk, AnalysisOutput, ChatSession → ChatMessage, Job |
| ChatSession | ChatMessage |
| Document | Chapter → Chunk |

All cascade-deleted records also trigger removal of associated files in `data/`.
