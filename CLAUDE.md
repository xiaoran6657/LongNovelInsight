# CLAUDE.md — LongNovelInsight Development Rules

## Project

LongNovelInsight is a local-first LLM-powered long-novel analysis tool.
Current version: **v0.4.0-dev**.

## Current State

**v0.3 Backend — COMPLETE.** **v0.3 Frontend — COMPLETE.** **v0.3.1 — COMPLETE.**
**v0.4 Backend — COMPLETE (Steps 1-10 of 10).** **v0.4 Frontend — COMPLETE (Steps 1-11 of 11).**
Multi-Work data model, Work CRUD, Work-scoped upload/parse/analysis, cross-work
entity registry, character graph, timeline, cross-work run orchestration,
work-scoped search/retrieve filters. Frontend: tab navigation, Work management,
cross-work dashboard with polling, entity registry, graph/timeline views,
work-scoped search + evidence UI.

What each version delivered:
- **v0.1**: Basic TXT analysis — 6 analysis types per chunk, evidence-grounded chat, keyword retrieval.
- **v0.2**: Staged map-reduce pipeline — `local_extraction` (1 LLM call/chunk) → deterministic `merge` → `final outputs`. ~4× token savings. AnalysisRun lifecycle (preview/range/full/incremental, retry/resume/cancel).
- **v0.3**: EPUB upload/parse, unified TXT/EPUB source abstraction, SQLite FTS5 full-text search with CJK fallback, hybrid retrieval (FTS + keyword + structured atoms/outputs), retrieval trace debugging, structured chat evidence, entity evidence explorer, similar scenes, semantic rerank skeleton. **Backend complete (12/12 steps). Frontend complete (12/12 steps).**
- **v0.3.1**: Transport error capture (`httpx.TransportError`), `finish_reason` truncation detection, adaptive retry token escalation (4096→8192→16384), per-attempt error re-evaluation, thinking mode warning + estimate buffer, prompt output size limits, causality multi-strategy matching (stable_id/title/id_hint/contains), final output warning consolidation, `_fail_run` protection for completed/partial_success runs, cumulative token accounting across all LLM attempts (reasoning/cache/unavailable breakdown), `_recalculate_run_usage_from_extractions` helper, cost estimate alignment with `max_output_tokens`/thinking/mode/retry, retry/resume usage persistence, DeepSeek cache field priority.

v0.3 progress detail: see `agent/PROJECT_STATUS.md` and `agent/NEXT_ACTIONS.md`.

## Tech Stack

- **Backend**: Python + FastAPI + SQLModel + SQLite. Flat structure: `main.py`, `config.py`, `db.py`, `routers/`, `models/`, `services/`, `tests/`. No `backend/app/` nesting.
- **Frontend**: React + TypeScript + Vite + TanStack Query + React Router DOM v7 + Plain CSS
- **LLM**: OpenAI-Compatible API (DeepSeek by default)
- **Quality**: pytest (724 + 5 integration) + Ruff (backend), tsc + ESLint + Vite build + 44 Playwright e2e (frontend)
- **Storage**: Local `data/` directory + SQLite. TXT files normalized to UTF-8; EPUB stored as-is.
- **Python env**: Conda environment `LongNovelInsight`
- **Key deps**: `fastapi`, `uvicorn`, `sqlmodel`, `httpx`, `python-multipart`, `beautifulsoup4`, `pytest`, `ruff`

## Architecture (Key Points)

### v0.2 Analysis Pipeline (the core engine)
```
POST /api/topics/{id}/analysis/runs
  → Stage 1: local_extraction (per chunk, parallel, LLM)
  → Stage 2: deterministic merge (per type, Python, no LLM)
  → Stage 3: final outputs (Python, v0.1-compatible AnalysisOutput)
```

### v0.3 Additions (Steps 1-12 complete)
- **Source abstraction**: `SourceDocument` / `SourceChapter` dataclasses — TXT and EPUB both produce these, then unified chapter/chunk creation.
- **EPUB parser**: `epub_parser_service.py` — zipfile + xml.etree.ElementTree for OPF/container, beautifulsoup4 for XHTML text extraction.
- **FTS5**: `fts_service.py` — `chunk_fts` virtual table, rebuild/delete/search with CJK keyword fallback.
- **Hybrid retrieval**: `retrieval_service.py` — multi-source candidates (FTS + keyword + structured atoms + analysis outputs), dedup, score normalization, RetrievalTrace.
- **Search/Retrieve/Locator APIs**: `POST /search`, `POST /retrieve`, `GET /metadata`, `GET /locator`.
- **Chat upgrade**: Structured evidence_json, hybrid retrieval with legacy fallback, empty-retrieval guard.
- **Entity evidence + Similar scenes**: `routers/entities.py` — `GET /entities/{id}/evidence`, `GET /similar-scenes`.
- **Semantic rerank skeleton**: `ENABLE_SEMANTIC_RERANK=False`, `EmbeddingProvider`, `EmbeddingCache` table.
- **v0.3.1 stability fixes**: Transport error capture, `finish_reason` truncation detection, adaptive retry escalation (4096→8192→16384), per-attempt error re-evaluation, thinking mode warning, prompt output limits, causality multi-strategy matching, warning consolidation, run status protection.
- **v0.3.1 token accounting**: Cumulative `AttemptUsage` across all LLM calls (not just last one), `LocalExtraction` fields for reasoning/cache/unavailable tokens, `_recalculate_run_usage_from_extractions`, cost estimate aligned with `max_output_tokens`/thinking/mode/retry multiplier, DeepSeek cache field priority, retry/resume usage persistence, UI token breakdown (total/input/output/reasoning).

### v0.4 Backend Additions (Steps 1-10 complete)
- **Multi-Work data model**: `Work`, `GlobalEntity`, `EntityMention`, `CrossWorkRun`, `GraphSnapshot`, `TimelineItem` — 6 new tables.
- **Work CRUD**: `routers/works.py` + `work_service.py` — default Work resolution, delete-safe behavior.
- **Work-scoped upload/parse/analysis**: Document stored per Work (`work_{id}_original.txt/epub`); parse cleanup scoped by document_id; analysis runs filtered by work_id.
- **Cross-work entity registry**: `cross_work_entity_service.py` — deterministic merge via stable_id/name/alias matching, type-conflict guards.
- **Character graph**: `cross_work_graph_service.py` — edges from relation atoms (primary) or event co-occurrence (fallback); `graph_snapshot` persistence.
- **Timeline**: `cross_work_timeline_service.py` — ordering by work.series_index × 1M + chapter × 1K + chunk; `timeline_item` persistence.
- **Cross-work run**: `cross_work_run_service.py` — orchestrate entity/graph/timeline builders; background thread execution.
- **Work filters**: Search/retrieve endpoints accept optional `work_ids`; results annotated with work metadata.

### v0.3 Frontend Additions (Steps 1-12 complete)
- **features/search/**: `TopicSearchPanel`, `SearchResultList`, `SearchResultCard`, `RetrievalMethodBadge`, `RetrievalDebugDrawer`
- **features/evidence/**: `EntityEvidencePanel`, `SimilarScenesPanel`
- **features/chat/**: `ChatEvidenceList` with `normalizeEvidence()` — structured evidence cards, backward-compatible with legacy `string[]`
- **features/document/**: `DocumentMetadataCard`
- **features/topic/**: `EpubChapterTree`, `SourceLocatorBadge` (enhanced `DocumentPanel`, `ChaptersPanel`)
- **api/**: `search.ts`, `retrieve.ts`, `entities.ts`, updated `types.ts`
- **e2e/**: `v0.3-features.spec.ts` — 11 tests (EPUB metadata, search, debug drawer, entity evidence, similar scenes, idle states)

### Key Modules
```
backend/
  main.py, config.py, db.py
  routers/   — health, topics, documents, parse, model_providers, provider_presets,
               topic_provider_config, analysis_jobs, analysis_outputs, analysis_runs,
               chat, search, retrieve, entities (v0.3), works, cross_work (v0.4)
  models/    — topic, document, chapter, chunk, model_provider, topic_provider_config,
               analysis_output, analysis_run, local_extraction, extracted_atom,
               analysis_artifact, chat, job, job_item, retrieval_trace,
               embedding_cache (v0.3), work, global_entity, entity_mention,
               cross_work_run, graph_snapshot, timeline_item (v0.4)
  services/  — 35 modules including parser_service, epub_parser_service,
               fts_service, retrieval_service, embedding_service (v0.3),
               analysis_run_service, merge_service, final_output_service,
               llm_client, chat_service, local_extraction_worker,
               work_service, cross_work_entity_service, cross_work_graph_service,
               cross_work_timeline_service, cross_work_run_service (v0.4)
```

Full architecture: `docs/ARCHITECTURE.md`. Data model: `docs/DATA_MODEL.md`. API reference: `docs/API.md`.

## Forbidden (v0.4.0)

Do NOT introduce or reference:
1. Login / auth / multi-user systems
2. Cloud sync / remote storage
3. Multiple source documents per Work
4. PDF parsing / OCR / DRM removal
5. Docker / containerization
6. LangChain / LLM frameworks
7. Vector databases (Chroma, Pinecone, Qdrant, FAISS, etc.)
8. Redis / Celery / PostgreSQL / message queues
9. Plugin systems
10. Complex abstractions or premature generalization
11. Any v0.5+ features (plugin marketplace, SaaS, remote storage)
12. Tailwind / MUI / Ant Design / Chakra / Redux / Zustand / MobX

## Commands

```bash
# Activate environment
conda activate LongNovelInsight

# Backend
cd backend
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run dev

# Tests
cd backend && pytest -v
cd frontend && npm run typecheck && npm run lint && npm run build

# Lint
cd backend && ruff check .
cd frontend && npx eslint src/

# Format
cd backend && ruff format .
cd frontend && npx prettier --write src/
```

## Pre-Commit Checklist

- [ ] pytest passes (backend)
- [ ] ruff check passes (backend)
- [ ] tsc --noEmit passes (frontend)
- [ ] eslint passes (frontend)
- [ ] vite build passes (frontend)
- [ ] No `data/`, `*.sqlite`, `*.txt` files staged
- [ ] No API keys or secrets in code
- [ ] No forbidden technologies introduced
- [ ] `agent/PROJECT_STATUS.md` updated
- [ ] `CLAUDE.md` updated if version/progress changed (update version, test count, step progress)

## Code Style

- Python: type hints on all function signatures
- TypeScript: strict mode, prefer `type` over `interface`
- No docstrings unless the WHY is non-obvious
- No dead code, no commented-out blocks
- Flat over nested; simple over clever

## Git

- Commit messages in English, imperative mood
- Never commit `data/`, `*.sqlite`, `*.txt`, `.env`, or API keys
- Co-authored-by: Claude <noreply@anthropic.com> on AI-assisted commits

## Detailed Docs

- Task planning: `agent/NEXT_ACTIONS.md`
- Detailed status: `agent/PROJECT_STATUS.md`
- Architecture decisions: `agent/DECISIONS.md`
- Operational rules: `agent/AGENT_RULES.md`
- Step prompts: `Prompts/V0.3/Backend_v0.3_Prompts.md`
- MVP specs: `MVP/v0.3.md`
- Roadmap: `docs/ROADMAP.md`
