# LongNovelInsight — Roadmap

## v0.1.0 (Current)

Single `.txt` novel analysis. This is the MVP.

- Upload one `.txt` novel per Topic.
- Auto-detect encoding (UTF-8 / GBK).
- Parse into chapters and chunks.
- Six LLM analysis types: overview, characters, relationships, events, causal chain, themes.
- Topic-level chat with evidence-grounded answers.
- Local SQLite + `data/` storage.
- LLM provider configuration (DeepSeek / OpenAI-compatible).
- Storage usage and job progress UI.

## v0.2.0 — EPUB Support

- Upload `.epub` novels.
- Parse EPUB structure (chapters, metadata).
- All v0.1.0 analysis types work on EPUB content.

## v0.3.0 — Multi-Book Topics

- One Topic can contain multiple novels.
- Cross-novel character matching and relationship detection.
- Cross-novel event timeline.

## v0.4.0 — Graph Visualization

- Interactive character relationship network graph.
- Event timeline visualization.
- Causal chain diagram.

## v0.5.0 — Vector Retrieval

- Chunk embeddings for semantic search.
- Vector-based context retrieval for chat (replaces keyword matching).
- "Find similar scenes" feature.

---

*Versions beyond v0.5.0 are not yet planned. Features listed here are subject to change based on user feedback.*
