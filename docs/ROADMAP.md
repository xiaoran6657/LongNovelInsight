# LongNovelInsight — Roadmap

## v0.1.0 (Current)

Single `.txt` novel analysis. This is the MVP.

- Upload one `.txt` novel per Topic.
- Auto-detect encoding (UTF-8 / GBK / GB18030 / UTF-16).
- Parse into chapters and chunks (idempotent, whitespace-normalized).
- Six LLM analysis types via async parallel jobs: overview, characters, relationships, events, causal chain, themes.
- Provider preset catalog (DeepSeek / OpenAI / Qwen / Moonshot / Custom).
- Topic-level provider config overrides (Model, Max Tokens, Temperature, Thinking).
- Topic-level chat with evidence-grounded Q&A, multi-turn history, message actions (copy/edit/delete).
- Per-message token usage tracking, per-model usage statistics.
- Local SQLite + `data/` storage with incremental schema migration.
- Storage usage and job progress UI.

## v0.2.0 — Scale & Depth

- EPUB support: parse EPUB structure (chapters, metadata), all v0.1 analysis types on EPUB content.
- Map-reduce analysis pipeline (local extraction per chunk → global merge) to handle novels of any size.
- Chunk / analysis output migration from SQLite BLOB columns to disk files.
- Prompt caching via repeated shared prefix (reduce token cost on repeat analysis runs).
- Max Tokens slider control with range bounds and drag-accelerated stepping.
- Stable entity ID system (pinyin-based character IDs, title-based event IDs).
- Frontend automated e2e tests (Playwright or similar).

## v0.3.0 — Multi-Book & Vector Retrieval

- One Topic can contain multiple novels.
- Cross-novel character matching and relationship detection.
- Cross-novel event timeline.
- Chunk embeddings for semantic search (replace keyword matching in chat retrieval).
- "Find similar scenes" feature.

## v0.4.0 — Visualization

- Interactive character relationship network graph.
- Event timeline visualization.
- Causal chain diagram.

---

*Versions beyond v0.4.0 are not yet planned. Features listed here are subject to change based on user feedback.*
