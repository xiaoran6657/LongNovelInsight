# Next Actions

**v0.3.1 COMPLETE.** **v0.4 Backend COMPLETE (Steps 1-10).** Next: v0.4 Frontend.

## Immediate Priority: v0.4 Frontend Implementation

### v0.4 Backend (10 steps) — COMPLETE

1. ✅ **Step 0** — `docs/v0.4/backend-step0-audit.md`
2. ✅ **Step 1** — Schema + migration
3. ✅ **Step 2** — Work CRUD + default Work
4. ✅ **Step 3** — Work-aware upload/parse
5. ✅ **Step 4** — Work-scoped analysis
6. ✅ **Step 5** — Entity registry builder
7. ✅ **Step 6** — Graph snapshot builder
8. ✅ **Step 7** — Timeline builder
9. ✅ **Step 8** — Cross-work run orchestration
10. ✅ **Step 9** — Search/retrieve work filters
11. ✅ **Step 10** — Documentation update

### v0.4 Frontend (8 steps)

1. **Step 0 — Audit & Plan:** Inspect routes, components, API patterns. Write `docs/v0.4/frontend-step0-audit.md`.
2. **Step 1 — API Types:** `src/api/works.ts`, `crossWork.ts`, `graphs.ts`, `timeline.ts`. Type definitions for all new endpoints.
3. **Step 2 — Work UI:** Work list, create form, detail panel. Empty state for legacy Topics.
4. **Step 3 — Work Upload + Analysis:** Upload panel per Work, parse/analyze entry points.
5. **Step 4 — Cross-Work Dashboard:** Stats summary, last run status, build trigger.
6. **Step 5 — Entity Registry:** Searchable/filterable table, detail drawer with aliases/mentions/evidence.
7. **Step 6 — Character Graph:** Cytoscape.js canvas, filters, node/edge evidence panels.
8. **Step 7 — Timeline:** Ordered list/rail, Work/participant filters, source locator links.
9. **Step 8 — E2E Tests + Docs:** 8+ Playwright tests (all mocked). Update README, smoke test doc.

### Execution Order

Backend Steps 1–4 first (Work data model + upload/parse/analysis usable).
Then Backend 5–8 (cross-work build).
Frontend steps in parallel after corresponding backend APIs exist.
Codex review after each commit.

---

## Completed

### v0.3.1 — Stability & Token Accounting (2026-06-03)

1. **LLM transport error capture:** ✅ `httpx.TransportError` caught and wrapped as `LLMClientError` with retry.
2. **finish_reason truncation detection:** ✅ `LLMResponse.finish_reason` tracked; `length`/token-near-max detected in error messages.
3. **Adaptive retry token escalation:** ✅ 4096→8192→16384. Per-attempt error re-evaluation. Longer 429 backoff.
4. **Thinking mode awareness:** ✅ Warning on `enabled`; `provider_default` unchanged; 1.4× cost estimate buffer.
5. **Prompt output limits:** ✅ Per-atom caps in `local_extraction.md`; evidence quote length limits.
6. **Causality matching:** ✅ Multi-strategy: stable_id, title, id_hints, substring containment (min 4 chars).
7. **Warning consolidation:** ✅ `build_final_causality` produces single summary line, not N warnings.
8. **Run status protection:** ✅ `_fail_run` blocks overwrite of SUCCEEDED/CANCELLED/PARTIAL_SUCCESS + completed metadata.
9. **Cumulative token accounting:** ✅ `AttemptUsage` dataclass; `LocalExtraction` new fields; `_recalculate_run_usage_from_extractions`.
10. **DeepSeek cache fields:** ✅ `prompt_cache_hit/miss_tokens` priority with OpenAI-style fallback.
11. **Retry/resume persistence:** ✅ New usage fields saved (`add` not `replace`); `_recalculate` called after retry/resume.
12. **Cost estimate alignment:** ✅ Backend + frontend use `max_output_tokens × 0.65 × retry_multiplier` with mode/thinking awareness.
13. **Frontend token breakdown:** ✅ UI shows total/input/output/reasoning; unavailable attempts warning.
14. **README updates:** ✅ Backend + frontend READMEs updated for v0.3.1.
15. **CLAUDE.md:** ✅ Updated for v0.3.1-dev.

### v0.3.0 — EPUB, Search & Evidence (2026-05-31)

- Backend Steps 0–12 complete.
- Frontend Steps 0–12 complete.
- Tagged `v0.3.0-rc1`.

### v0.2.0 — Staged Analysis Pipeline (2026-05-26)

- Backend Steps 0–14 complete.
- Frontend Steps 0–13 complete.
- Tagged `v0.2.0`.

---

## v0.4 Planning — COMPLETE

See `MVP/v0.4.md` for full spec, `Prompts/V0.4/` for step-level prompts, and `docs/ROADMAP.md` for version roadmap.

### What v0.4 delivers

| Area | v0.3.1 (current) | v0.4.0 (target) |
|------|-------------------|-----------------|
| Data model | Topic 1↔1 Document | Topic 1→* Work, Work 1→0..1 Document |
| Upload | Per Topic | Per Work (legacy → default Work) |
| Analysis | Per Topic | Per Work + cross-work build |
| Entities | Chunk-level atoms only | Topic-level global registry with mentions |
| Relationships | Merge outputs only | Graph snapshots with evidence edges |
| Events | Per-chunk extraction | Ordered timeline with cross-work support |
| Visualization | List/search cards | Cytoscape graph + timeline view |

### Key design principles

- Deterministic cross-work aggregation (no new LLM calls).
- Evidence-first: every entity/graph/timeline node links back to source chunks.
- Backward compatible: existing v0.3 APIs and databases continue to work.
- Incremental: one default Work per legacy Topic, no forced migration.

### Files

- Spec: `MVP/v0.4.md`
- Backend prompts: `Prompts/V0.4/Backend_v0.4_Prompts.md`
- Frontend prompts: `Prompts/V0.4/Frontend_v0.4_Prompts.md`
- Review prompts: `Prompts/V0.4/Codex_v0.4_Review_Prompts.md`
- Roadmap: `docs/ROADMAP.md`
