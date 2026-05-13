# LongNovelInsight v0.1.0 — LLM Analysis Pipeline

## Overview

The pipeline takes a parsed novel (chapters + chunks) and runs six independent analysis types against the configured LLM. Each analysis type has a specific prompt, output schema, and evidence requirements.

## Principles

1. **Evidence-grounded**: Every claim about the novel MUST be backed by `source_chunk_ids` and `evidence_quotes` — direct quotes from the original text.
2. **Confidence required**: Each output item includes a `confidence` score (0.0–1.0). Low-confidence items are still stored but flagged in the UI.
3. **No fabrication**: The LLM MUST NOT invent characters, events, relationships, or themes not present in the source text. The system prompt explicitly instructs against hallucination.
4. **Structured output**: All LLM responses must be valid JSON matching the predefined schema. Malformed JSON triggers a retry (max 2 retries).

## Pipeline Steps

### Step 0: Novel Parsing (Pre-LLM)

Before any LLM call, the novel is processed:

1. **Encoding detection**: Sample first 4 KB, detect UTF-8 vs GBK. Convert to UTF-8 if needed.
2. **Chapter splitting**: Apply regex patterns to find chapter boundaries:
   - `第[一二三四五六七八九十百千0-9]+[章节回]` (Chinese)
   - `Chapter\s+\d+` (English)
   - `CHAPTER\s+\d+` (English)
   - Fallback: split by double-newline clusters if no chapters detected.
3. **Chunking**: Each chapter is split into overlapping chunks:
   - Target chunk size: ~4000 tokens (estimated via character count / 1.5 for Chinese, character count / 4 for English).
   - Overlap: ~200 tokens between consecutive chunks.
   - Chunks never cross chapter boundaries.
   - Each chunk is saved as `data/chunks/{chunk_id}.txt`.

### Step 1–6: LLM Analysis Types

Each analysis type uses a two-part prompt:
- **System prompt**: Describes the role, task, output JSON schema, and anti-fabrication rules.
- **User prompt**: Contains the chunk texts (up to context window limit) and instructs the model to analyze them.

If the novel has more chunks than fit in a single context window, the caller batches chunks into multiple LLM calls and merges/deduplicates the results.

---

### Analysis 1: Work Overview (`overview`)

**Purpose:** A high-level summary of the novel's plot, style, narrative structure, and key features.

**Input:** Selected chunks from the first chapter (for style/intro), middle chapters (evenly sampled), and final chapter (for ending).

**Output Schema:**
```json
{
  "analysis_type": "overview",
  "results": {
    "title": "三国演义",
    "author_hint": "罗贯中",
    "era_setting": "东汉末年",
    "genre_tags": ["历史演义", "战争", "政治谋略"],
    "one_paragraph_summary": "...",
    "narrative_structure": "章回体, 120回",
    "style_notes": "文白夹杂, 说书人口吻...",
    "key_themes_brief": ["天下大势分久必合", "忠义"],
    "total_chapters_analyzed": 120,
    "source_chunk_ids": ["uuid1", "uuid3", "uuid120"],
    "evidence_quotes": ["话说天下大势，分久必合，合久必分"],
    "confidence": 0.85
  }
}
```

---

### Analysis 2: Character List (`characters`)

**Purpose:** Extract all named characters with descriptions, traits, roles, and first-appearance evidence.

**Input:** All chunks (batched). Deduplication step merges mentions of the same character across batches.

**Output Schema:**
```json
{
  "analysis_type": "characters",
  "results": [
    {
      "name": "刘备",
      "aliases": ["刘玄德", "刘皇叔"],
      "description": "蜀汉开国皇帝...",
      "traits": ["仁德", "坚忍", "知人善任"],
      "role": "protagonist",
      "first_appearance_chapter": 1,
      "source_chunk_ids": ["uuid1", "uuid15"],
      "evidence_quotes": ["那人平生不甚好读书；性宽和，寡言语...", "..."],
      "confidence": 0.95
    }
  ]
}
```

---

### Analysis 3: Character Relationships (`relationships`)

**Purpose:** Identify pairwise relationships between characters.

**Input:** Completed character list + all chunks (batched).

**Output Schema:**
```json
{
  "analysis_type": "relationships",
  "results": [
    {
      "character_a": "刘备",
      "character_b": "关羽",
      "relationship_type": "结义兄弟",
      "description": "桃园三结义中的大哥与二弟，生死相托的君臣兼兄弟关系。",
      "direction": "bidirectional",
      "source_chunk_ids": ["uuid1", "uuid25"],
      "evidence_quotes": ["次日，于桃园中，备下乌牛白马祭礼等项，三人焚香再拜而说誓曰..."],
      "confidence": 0.95
    }
  ]
}
```

---

### Analysis 4: Key Events (`events`)

**Purpose:** Extract major plot events in chronological order.

**Input:** All chunks (batched, ordered by chapter/chunk index).

**Output Schema:**
```json
{
  "analysis_type": "events",
  "results": [
    {
      "event_id": "evt_001",
      "title": "桃园三结义",
      "chapter": 1,
      "summary": "刘备、关羽、张飞在桃园结为兄弟，立誓共扶汉室。",
      "participants": ["刘备", "关羽", "张飞"],
      "importance": "critical",
      "source_chunk_ids": ["uuid1"],
      "evidence_quotes": ["念刘备、关羽、张飞，虽然异姓，既结为兄弟，则同心协力，救困扶危..."],
      "confidence": 0.95
    }
  ]
}
```

---

### Analysis 5: Event Causal Chain (`causal_chain`)

**Purpose:** Identify causal links between key events — "A caused B", "B led to C".

**Input:** Completed key events list + event-surrounding chunks.

**Output Schema:**
```json
{
  "analysis_type": "causal_chain",
  "results": [
    {
      "cause_event_id": "evt_005",
      "effect_event_id": "evt_012",
      "causal_description": "董卓专权导致十八路诸侯联合讨伐。",
      "causal_strength": "direct",
      "source_chunk_ids": ["uuid10", "uuid20"],
      "evidence_quotes": ["..."],
      "confidence": 0.85
    }
  ]
}
```

---

### Analysis 6: Theme / Philosophy (`themes`)

**Purpose:** Identify major themes, philosophical ideas, and moral frameworks in the novel. Analyze how they are expressed through plot, characters, and dialogue.

**Input:** Selected chunks from key chapters + work overview + character list.

**Output Schema:**
```json
{
  "analysis_type": "themes",
  "results": [
    {
      "theme_name": "忠义观",
      "description": "小说通过关羽、诸葛亮等人物的行为，构建了一套以'忠义'为核心的价值体系...",
      "related_characters": ["关羽", "诸葛亮", "刘备"],
      "related_chapters": [25, 26, 27, 77],
      "philosophical_framework": "儒家忠孝伦理 + 民间侠义传统",
      "source_chunk_ids": ["uuid50", "uuid150"],
      "evidence_quotes": ["吾今遇害，虽死无悔，但恐兄长不知..."],
      "confidence": 0.9
    }
  ]
}
```

---

## Anti-Fabrication Rules (Included in Every System Prompt)

```
RULES:
1. Only report information EXPLICITLY present in the provided text.
2. If you are unsure about a detail, set confidence < 0.5 and note your uncertainty.
3. Every claim MUST include at least one direct quote from the source text as evidence.
4. Do NOT invent characters, events, relationships, or themes not mentioned in the text.
5. If the text provides insufficient information for a field, use null — do NOT guess.
6. Output must be valid JSON matching the schema exactly.
```

## LLM Client Wrapper

All LLM calls go through a single `llm_client.py` module (`backend/services/llm_client.py`):

- **Class**: `OpenAICompatibleLLMClient(base_url, api_key, timeout=120.0, max_retries=2)`
- **Endpoint**: `{provider.base_url}/chat/completions` — the base_url should already include `/v1` if needed.
- **Request format**: OpenAI-compatible chat completions. Headers: `Authorization: Bearer {api_key}`, `Content-Type: application/json`.
- **Retry logic**: 2 retries on network/timeout errors and JSON parse failures, with 1s/2s backoff.
- **Timeout**: 120 seconds per request (configurable).
- **Sync only**: v0.1.0 uses sync `httpx.Client`. No async needed.
- **No streaming**: All calls wait for the full response.
- **API key safety**: The client never logs the raw API key. The `provider_test_service` sanitizes error messages via `mask_api_key()`.
- **Tests**: All tests mock `httpx.post` via `monkeypatch`. No real external API calls in CI.

## Pipeline Orchestration (v0.1.0)

v0.1.0 runs analysis synchronously via `POST /api/topics/{topic_id}/analysis/run`:

1. Delete previous analysis outputs for the topic.
2. Select provider: prefer `topic.provider_id`, fall back to `is_default=true`.
3. Load the first `limit_chunks` (default 5) from the database ordered by chapter/chunk index.
4. For each of 6 analysis types:
   a. Load the corresponding prompt template from `backend/prompts/`.
   b. Build system + user messages with chunk context.
   c. Call LLM via `OpenAICompatibleLLMClient.chat()` with `response_format={"type":"json_object"}`.
   d. Parse JSON response, extract evidence_quotes, source_chunk_ids, confidence.
   e. Save `AnalysisOutput` row to SQLite.
   f. On failure (LLM error, JSON parse error): log and continue to next type.
5. Return all generated outputs.

Each output is stored in the `analysis_output` table with:
- `content_json` — the full LLM response as JSON
- `source_chunk_ids` — array of chunk IDs used as sources
- `evidence_quotes` — direct quotes extracted from the LLM response
- `confidence` — overall confidence score

## Evidence-Based Chat (v0.1.0)

The chat flow uses keyword retrieval to ground LLM answers in source material:

1. User sends a message via `POST /api/chat/sessions/{session_id}/messages`.
2. `retrieval_service.build_evidence_context()` performs keyword-based search:
   - **Chunks**: substring matching, Chinese character overlap, word-level overlap — scored and ranked.
   - **Analysis outputs**: content and title matching against the query.
3. The top-k chunk excerpts and analysis excerpts are assembled into an evidence context.
4. The LLM receives a system prompt instructing it to answer based only on evidence, outputting JSON with `answer`, `evidence`, and `uncertainty` fields.
5. The assistant message is saved with `evidence_json` and `uncertainty` preserved.
6. No vector embeddings are used — keyword retrieval is sufficient for v0.1.0.
