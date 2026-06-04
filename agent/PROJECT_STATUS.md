# Project Status — LongNovelInsight

## Current

- **Version:** v0.4.0-dev
- **Stage:** v0.4.0-dev. Backend complete (Steps 1-10). Frontend complete (Steps 1-11) with known limitations.
- **Tests:** Backend 724 pytest + 5 integration. Frontend typecheck/lint/build pass. Frontend 44 Playwright e2e (38 v0.3 + 6 v0.4).
- **Verdict:** PASS_WITH_KNOWN_LIMITATIONS — no P0 blockers; build & regression tests pass; MVP UI wired.
- **Performance:** Run history uses SQL-level pagination (limit/offset) + `useInfiniteQuery`. Hybrid retrieval latency ~1ms locally.
- **Release:** `v0.3.0` tagged. `v0.3.1` changes committed (not yet tagged).

## v0.3.1 — Complete (2026-06-03)

- [x] LLM transport error capture (`httpx.TransportError` → `LLMClientError`)
- [x] `finish_reason` truncation detection (length/completion_tokens near max)
- [x] Adaptive retry token escalation (4096→8192→16384, per-attempt re-evaluation)
- [x] Thinking mode awareness (warning + 1.4× cost estimate buffer)
- [x] Prompt output size limits (per-atom caps, evidence quote limits)
- [x] Causality multi-strategy matching (stable_id/title/id_hint/contains)
- [x] Final output warning consolidation (single summary line vs. N warnings)
- [x] Run status protection (`_fail_run` blocks completed/partial_success)
- [x] Cumulative token accounting (`AttemptUsage`, all LLM attempts summed)
- [x] `LocalExtraction` new fields: reasoning_tokens, cache, unavailable, attempt_usage_json
- [x] `_recalculate_run_usage_from_extractions` helper
- [x] DeepSeek cache field priority (prompt_cache_hit/miss_tokens → prompt_tokens_details fallback)
- [x] Retry/resume usage persistence (add not replace, recalculation after retry/resume)
- [x] Cost estimate alignment (max_output_tokens × 0.65 × retry_multiplier, mode-based, thinking buffer)
- [x] Frontend token breakdown UI (total/input/output/reasoning, unavailable warning)
- [x] Release notes: `docs/releases/v0.3.1.md`
- [x] README updates (backend + frontend)
- [x] CLAUDE.md updated

## v0.4 Backend — Complete (2026-06-03)

- [x] Step 0: Audit & plan (`docs/v0.4/backend-step0-audit.md`)
- [x] Step 1: Schema + migration (Work, GlobalEntity, EntityMention, CrossWorkRun, GraphSnapshot, TimelineItem)
- [x] Step 2: Work CRUD + default Work resolution
- [x] Step 3: Work-aware upload/parse
- [x] Step 4: Work-scoped v2 analysis
- [x] Step 5: Cross-work entity registry builder
- [x] Step 6: Character relationship graph snapshots
- [x] Step 7: Cross-work timeline builder
- [x] Step 8: Cross-work run orchestration
- [x] Step 9: Search/retrieve work-scope filters + docs update
- [x] Step 10: Documentation update (README, CLAUDE, PROJECT_STATUS, NEXT_ACTIONS)

## v0.4 Frontend — Complete with Known Limitations (2026-06-04)

- [x] Step 0: Audit & plan (`docs/v0.4/frontend-step0-audit.md`)
- [x] Step 1: API types + 4 client modules (works, crossWork, graphs, timeline)
- [x] Step 2: Work list/create/edit/delete + tab navigation in TopicDetailPage
- [x] Step 3: Work upload/parse/analysis entry points + WorkDetail
- [x] Step 4: Cross-work dashboard (run polling, warnings, stats, build trigger)
- [x] Step 5: Entity registry table (search/filter/sort, detail drawer with mentions)
- [x] Step 6: Character graph (edge table MVP, error state)
- [x] Step 7: Timeline view (ordered list, error state)
- [x] Steps 2-3 e2e: 6 tests (create/edit/delete forms, POST/PATCH body, delete 409/success)
- [x] Step 8: Documentation update (frontend README, PROJECT_STATUS, CLAUDE.md)
- [x] Step 9: Work scope in search results + chat evidence (work badges, work_ids filter)
- [x] Step 10: UX hardening (empty/error states verified, zero-Works/no-run crash safe)
- [x] Step 11: Final documentation + full regression (44 e2e, typecheck/lint/build clean)

**Known Limitations (v0.4 Frontend):**
- Step 3 upload/parse/analysis endpoints lack mocked e2e coverage (buttons gated on WorkCard click in mocked env).
- Graph tab currently renders edge table (Cytoscape visualization was planned per audit doc but not yet integrated).
- Timeline tab uses fixed limit:100 list, no pagination/evidence expand controls.

## v0.3.0 — Complete (2026-05-31)

- [x] Step 0: Audit & plan
- [x] Step 1: Schema Foundation
- [x] Step 2: Upload Layer (.epub)
- [x] Step 3: EPUB Parser Core
- [x] Step 4: Unified Parse Pipeline
- [x] Step 5: FTS Index Service
- [x] Step 6: Search / Metadata / Locator API
- [x] Step 7: Hybrid Retrieval + RetrievalTrace
- [x] Step 8: Chat Integration (structured evidence_json)
- [x] Step 9: Entity Evidence / Similar Scenes
- [x] Step 10: Optional Semantic Rerank skeleton
- [x] Step 11: Smoke Tests / Benchmarks
- [x] Step 12: Final Documentation Pass
- [x] Frontend v0.3 complete (12/12 steps)

## v0.2.0 — Complete

- [x] Staged pipeline: local_extraction → merge → final outputs
- [x] AnalysisRun lifecycle (preview/range/full/incremental)
- [x] Retry/Resume/Cancel with idempotency

## v0.1.0 — Complete

- [x] Basic TXT analysis (6 types), evidence-grounded chat, keyword retrieval

---

## v0.4 — Planning Complete

### Scope

v0.4 turns LongNovelInsight from a single-novel analyzer into a multi-work story-universe workspace.

**MVP Must-Have:**
- Multi-Work data model: Topic 1→* Work, Work 1→0..1 Document
- Existing single-document Topics auto-migrate to one default Work
- Work CRUD + Work-scoped upload/parse/analysis
- Topic-level cross-work entity registry (deterministic, no new LLM calls)
- Character relationship graph snapshots (Cytoscape.js frontend)
- Timeline items from event/causality atoms
- Cross-work build run orchestration
- Frontend: Work management, entity registry table/drawer, graph, timeline, dashboard

**Non-Goals:**
- No vector DB, graph DB, or embedding requirement
- No LLM-dependent entity resolution
- No multiple source documents per Work
- No manual entity merge/split UI in MVP
- No causal graph unless data is reliable

### Backend Implementation Steps (from `Prompts/V0.4/Backend_v0.4_Prompts.md`)

| Step | Description |
|------|-------------|
| 0 | Audit & plan (`docs/v0.4/backend-step0-audit.md`) |
| 1 | Schema + migration (work, global_entity, entity_mention, cross_work_run, graph_snapshot, timeline_item) |
| 2 | Work CRUD + default Work resolution |
| 3 | Work-aware document upload/parse |
| 4 | Work-scoped v2 analysis |
| 5 | Cross-work entity registry builder |
| 6 | Graph snapshot builder (character relationship) |
| 7 | Timeline builder |
| 8 | Cross-work run orchestration API |
| 9 | Search/retrieval/chat scope filters (optional for MVP) |
| 10 | Tests + documentation |

### Frontend Implementation Steps (from `Prompts/V0.4/Frontend_v0.4_Prompts.md`)

| Step | Description |
|------|-------------|
| 0 | Audit & plan (`docs/v0.4/frontend-step0-audit.md`) |
| 1 | API types + client modules (works, crossWork, graphs, timeline) |
| 2 | Work list + detail UI |
| 3 | Work upload panel + parse/analysis entry points |
| 4 | Cross-work dashboard |
| 5 | Entity registry table + detail drawer |
| 6 | Character relationship graph (Cytoscape.js) |
| 7 | Timeline view |
| 8 | E2E tests + documentation |

### New Data Model (6 new tables)

| Table | Purpose |
|-------|---------|
| `work` | One novel/volume inside a Topic |
| `global_entity` | Topic-level entity registry across Works |
| `entity_mention` | Evidence-linked mentions per Work |
| `cross_work_run` | Deterministic cross-work build job tracking |
| `graph_snapshot` | Cached derived graph JSON for visualization |
| `timeline_item` | Topic-level ordered event timeline |

### New Backend Services

| Service | Purpose |
|---------|---------|
| `work_service.py` | Work CRUD, default Work resolution, migration |
| `cross_work_entity_service.py` | Deterministic global entity registry build |
| `cross_work_graph_service.py` | Graph snapshot construction |
| `cross_work_timeline_service.py` | Timeline item construction |
| `cross_work_run_service.py` | Run orchestration/status/warnings |

### New Frontend Modules

| Module | Purpose |
|--------|---------|
| `src/api/works.ts` | Work CRUD + upload |
| `src/api/crossWork.ts` | Cross-work run endpoints |
| `src/api/graphs.ts` | Character/causal graph |
| `src/api/timeline.ts` | Timeline endpoint |
| `src/features/works/` | Work list, cards, forms |
| `src/features/crossWork/` | Dashboard, run panel |
| `src/features/entities/` | Global entity registry |
| `src/features/graphs/` | Cytoscape graph + filters |
| `src/features/timeline/` | Timeline list/rail |

### New Dependencies

| Dep | Purpose | Decision |
|-----|---------|----------|
| `cytoscape` | Character relationship graph | Recommended |
| `react-cytoscapejs` | React wrapper (optional) | Only if compatible with setup |
| `@xyflow/react` | Causal graph | Only if causal graph endpoint built |

---

## Known Scope Limitations

- **Semantic rerank disabled:** `ENABLE_SEMANTIC_RERANK=False` by default.
- **Final outputs:** v0.2 produces the same 6 output types as v0.1 (overview, characters, relations, events, causality, themes). Worldbuilding and foreshadowing have merge support but no final output builders. Timeline and character_arcs not yet implemented.
- **Multi-Work (v0.4):** One Topic can contain multiple Works, each with one Document.
- **No embeddings/vector search:** FTS5 + keyword + structured retrieval only.
- **Retry attempt_usage_json not merged:** New retries replace old attempt history (totals are correct via `+=`).
- **v0.4 Frontend known limitations:**
  - Upload/parse/analysis e2e not mocked (buttons require WorkCard selection in mocked Playwright env).
  - Character graph renders edge table (Cytoscape visualization planned per audit doc, not yet integrated).
  - Timeline is fixed-limit list without pagination or evidence expand controls.

## Release Info

- **Current tag:** v0.3.0
- **Branch:** main

## Tech Stack

Python + FastAPI + SQLModel + SQLite | React + TypeScript + Vite + TanStack Query | pytest + Ruff
