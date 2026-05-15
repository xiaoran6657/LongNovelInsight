# Input Contract (shared by all analysis prompts)

The backend provides novel text in the following format.

## Chunk format

Each chunk is identified by a bracketed header line followed by the source text:

```text
[chunk_id=uuid chapter_index=N chunk_index=M]
source text content (Chinese or other language)
```

- chunk_id: a UUID that uniquely identifies this chunk. Only these IDs are valid as source_chunk_ids.
- chapter_index: the chapter number (0-indexed).
- chunk_index: the chunk number within the chapter (0-indexed).

Multiple chunks are separated by blank lines.

## Analysis scope

The task_context indicates the current scope:
- batch_level: analyzing a selected subset of chunks (e.g., the first N chunks of the text).

## output_language

The output language is zh-CN. Write all analytical descriptions, summaries, and labels in Chinese. Preserve names, quotes, and evidence in the original source language.

## Known entities (optional, may not be provided)

If the backend provides known_characters or known_events, they appear as JSON arrays. Use them to supplement your extraction. If not provided, extract entities independently from the text.
