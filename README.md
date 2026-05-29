# LongNovelInsight

LongNovelInsight is a local-first tool that uses LLMs to analyze long novels (.txt and .epub) and produce structured insights — character profiles, relationship maps, key events, causal chains, and thematic analysis — all stored on your own machine.

## v0.3.0-dev (current)

Backend v0.3 is complete (Steps 1–12). Frontend v0.2 is complete. v0.3 adds EPUB support, SQLite FTS5 full-text search, hybrid retrieval across chunks/atoms/outputs, structured chat evidence, entity evidence explorer, similar scenes, optional semantic rerank skeleton, and retrieval trace debugging.

### What's New in v0.3 Backend

- **EPUB support**: Upload and parse .epub files. Metadata extraction (title, creator, language), spine-order chapter detection, XHTML text extraction. Unified `SourceDocument`/`SourceChapter` abstraction shared with TXT.
- **Source locators**: Every chunk has a `source_locator_json` field tracing back to its origin (EPUB href or TXT chapter offset), enabling precise evidence navigation.
- **FTS5 full-text search**: SQLite FTS5 virtual table over chunk text/titles with Unicode61 tokenizer. CJK keyword fallback with AND-group character overlap for unsegmented queries.
- **Hybrid retrieval**: Multi-source candidate generation — FTS, keyword fallback, structured atom search (canonical name/aliases/evidence), analysis output search. Dedup by chunk_id, min-max score normalization. RetrievalTrace persisted per retrieval for debugging.
- **Structured chat evidence**: `evidence_json` stored as structured objects (`text`, `source_type`, `chunk_id`, `method`, `score`, `locator`) instead of plain strings. Legacy string-array format still readable. Empty retrieval short-circuits LLM to prevent hallucination.
- **Search / Retrieve / Locator APIs**: `POST /search` (FTS + keyword), `POST /retrieve` (hybrid with optional trace), `GET /chunks/{id}/locator` (source position + excerpt).
- **Entity evidence**: `GET /entities/{id}/evidence` — find all evidence for an entity by atom id, stable_id, or canonical name. Returns matching atoms, source chunks (topic-isolated), and related analysis outputs.
- **Similar scenes**: `GET /similar-scenes` — by chunk_id (builds query seed from chunk text + atom names, excludes self) or free-text query. Lexical + structured similarity, no embeddings.
- **Optional semantic rerank**: `ENABLE_SEMANTIC_RERANK=False` feature flag with `EmbeddingProvider` skeleton and `EmbeddingCache` table. `/retrieve` accepts `semantic_rerank` method; returns warning when disabled.
- **Document metadata**: `GET /documents/current/metadata` returns parsed EPUB metadata or empty object for TXT.

### v0.3 Backend API Summary

| Area | Endpoints |
|------|-----------|
| Document | `GET /documents/current/metadata` |
| Search | `POST /search` (FTS + keyword fallback) |
| Retrieve | `POST /retrieve` (hybrid: FTS + keyword + structured + analysis_output + optional semantic_rerank) |
| Locator | `GET /chunks/{chunk_id}/locator` |
| Entity Evidence | `GET /entities/{entity_id}/evidence` |
| Similar Scenes | `GET /similar-scenes?chunk_id=...&query=...` |
| Chat (upgraded) | Structured evidence_json, RetrievalTrace per message, empty-retrieval guard |

### What It Does NOT Do (v0.3.0-dev)

- No PDF/OCR parsing, no DRM removal, no multi-book Topic, no cross-work analysis, no vector DB (Qdrant/Chroma/FAISS), no Docker, no LangChain/LlamaIndex, no graph visualization, no cloud sync/auth.

### You Bring Your Own API Key

LongNovelInsight is a local tool. You provide your own LLM API key (DeepSeek or any OpenAI-compatible provider). Your key stays on your machine and is never sent anywhere else.

### Copyright Notice

**Do not upload copyrighted novels that you do not have the rights to.** This tool is designed for analyzing public domain works, your own original writing, or works you are legally authorized to process. The repository itself does not contain any novel text.

## Tech Stack

| Layer    | Technology                          |
| -------- | ----------------------------------- |
| Backend  | Python + FastAPI + SQLModel + SQLite |
| Frontend | React + TypeScript + Vite           |
| LLM      | OpenAI-Compatible API (DeepSeek by default) |
| Quality  | pytest + Ruff                       |
| Storage  | Local `data/` directory + SQLite    |

## Quick Start

```bash
# Terminal 1 — Backend (Python + FastAPI)
cd backend
conda activate LongNovelInsight
pip install -e ".[dev]"
python -m uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/health

# Terminal 2 — Frontend (React + TypeScript + Vite)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Set your API key before running real LLM analysis or chat:

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
# Linux / macOS / Git Bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

## Development

See [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md) for the development process with Claude Code.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the version roadmap.

## Smoke Tests

### Frontend (manual walkthrough)

A step-by-step manual smoke test covering the full product workflow (health, provider, topic, upload, parse, analysis, chat, cleanup) is at [docs/FRONTEND_SMOKE_TEST.md](docs/FRONTEND_SMOKE_TEST.md). Run through it after any significant frontend change.

### Backend (automated scripts + pytest integration)

v0.1 smoke test at `backend/scripts/smoke_backend.py`. v0.2 smoke test at `backend/scripts/smoke_v2_backend.py`. v0.3 smoke test at `backend/tests/integration/test_v03_smoke.py` (pytest + TestClient, no live server). See [docs/SMOKE_TEST.md](docs/SMOKE_TEST.md) for details.

```bash
# v0.1 safe-mode smoke test (no real LLM calls):
cd backend
python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --cleanup

# v0.2 safe-mode smoke test:
python scripts/smoke_v2_backend.py --base-url http://127.0.0.1:8000 --cleanup

# v0.3 smoke test (pytest, no live server needed):
cd backend
conda run -n LongNovelInsight python -m pytest tests/integration/test_v03_smoke.py -v -s -m integration
```

## v0.1.0 Feature Checklist

### Provider Management
- [x] Create provider with preset (DeepSeek/OpenAI/Qwen/Moonshot/Custom)
- [x] Base URL and model dropdowns auto-populate from preset
- [x] Manual base URL and model name editing
- [x] Optional advanced fields (context window, max tokens, temperature)
- [x] API key masked in list (`sk-...abcd`), never returned by API
- [x] Connection test with API consumption warning
- [x] Edit / delete provider (blocked if bound to a Topic)

### Topic Management
- [x] Create / list / detail / delete Topic
- [x] Bind / re-bind Provider
- [x] Document upload (.txt, UTF-8/GBK/GB18030/UTF-16 → UTF-8)
- [x] Delete document with full cascade

### Parse & Storage
- [x] Parse novel → chapters + overlapping chunks
- [x] View chapters list with titles and char counts
- [x] View chunks with text preview toggle
- [x] Storage breakdown (novel / chunks / analyses / DB)
- [x] Idempotent: re-parse returns existing results unless forced
- [x] Whitespace normalization (excessive blank lines collapsed)

### Analysis
- [x] Run structured analysis (6 types via async parallel jobs)
- [x] Adjustable limit_chunks with token cost estimate
- [x] Provider Config panel: Model / Max Tokens / Temperature / Thinking with presets
- [x] Model recommendation based on document size (Fast / Quality presets)
- [x] Per-type output cards with evidence, confidence, source chunk IDs
- [x] Retry failed types / Re-analyze with deepen mode
- [x] Progress bar with per-type completion polling
- [x] Summary bar: elapsed time, real token usage, per-type status

### Chat
- [x] Session CRUD with collapsible sidebar
- [x] Evidence-grounded Q&A with retrieval context
- [x] Multi-turn conversation history (last 6 messages)
- [x] Message actions: copy, inline edit & resend, delete
- [x] Optimistic user message display
- [x] Auto-height input with distinct background
- [x] Collapsible right panel with draggable dividers
- [x] Right panel: editable Provider Config + per-model usage stats
- [x] Right panel: source text viewer
- [x] Token usage tracked per message (prompt / completion / total) by model

## License

AGPL-3.0 — see [LICENSE](LICENSE).
