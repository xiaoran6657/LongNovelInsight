# Next Actions

**v0.4 Backend COMPLETE (Steps 1-10).** **v0.4 Frontend COMPLETE (Steps 1-11).** Next: v0.4.0 release tagging + v0.4.1 hardening.

## Immediate Priority: v0.4.0 Release

1. Tag `v0.4.0` after final integration test pass.
2. Write release notes summarizing all v0.4 backend + frontend changes.
3. Run full regression: backend pytest, frontend typecheck/lint/build/e2e.

### v0.4.1 Hardening (candidate items)

- Cytoscape.js integration for character graph visualization.
- Timeline pagination and evidence/source locator expand controls.
- Upload/parse/analysis e2e tests (currently unreliable in mocked Playwright env).
- Work-scoped chat evidence filtering.
- Retry attempt_usage_json merging for complete audit trail.

---

## Completed

### v0.4 Frontend (11 steps) — COMPLETE (2026-06-04)

| Step | Description | Status |
|------|-------------|--------|
| 0 | Audit & plan (`docs/v0.4/frontend-step0-audit.md`) | ✅ |
| 1 | API types + 4 client modules (works, crossWork, graphs, timeline) | ✅ |
| 2 | Work list/create/edit/delete + tab navigation in TopicDetailPage | ✅ |
| 3 | Work upload/parse/analysis entry points + WorkDetail | ✅ |
| 4 | Cross-work dashboard (run polling, warnings, stats, build trigger) | ✅ |
| 5 | Entity registry table (search/filter/sort, detail drawer with mentions) | ✅ |
| 6 | Character graph (edge table, error state) | ✅ |
| 7 | Timeline view (ordered list, error state) | ✅ |
| 8 | E2E tests + docs (6 Work CRUD + form body tests) | ✅ |
| 9 | Work scope in search results + chat evidence | ✅ |
| 10 | UX hardening (empty/error states, zero-Works safety, search clear) | ✅ |
| 11 | Documentation finalization + full regression | ✅ |

### v0.4 Backend (10 steps) — COMPLETE (2026-06-03)

| Step | Description | Status |
|------|-------------|--------|
| 0 | Audit & plan (`docs/v0.4/backend-step0-audit.md`) | ✅ |
| 1 | Schema + migration (6 new tables, document rebuild) | ✅ |
| 2 | Work CRUD + default Work resolution | ✅ |
| 3 | Work-aware upload/parse (scoped source files, delete scope) | ✅ |
| 4 | Work-scoped v2 analysis | ✅ |
| 5 | Cross-work entity registry builder (deterministic merge) | ✅ |
| 6 | Character relationship graph snapshots | ✅ |
| 7 | Cross-work timeline builder | ✅ |
| 8 | Cross-work run orchestration | ✅ |
| 9 | Search/retrieve work-scope filters | ✅ |
| 10 | Documentation (README, CLAUDE, PROJECT_STATUS, NEXT_ACTIONS) | ✅ |

### v0.3.1 — Stability & Token Accounting (2026-06-03)

15 items covering transport errors, truncation detection, adaptive retry,
thinking mode awareness, prompt output limits, causality matching,
warning consolidation, run status protection, cumulative token accounting,
DeepSeek cache fields, retry/resume persistence, cost estimate alignment,
frontend token breakdown, README updates.

### v0.3.0 — EPUB, Search & Evidence (2026-05-31)

Backend Steps 0-12 complete. Frontend Steps 0-12 complete. Tagged `v0.3.0-rc1`.

### v0.2.0 — Staged Analysis Pipeline (2026-05-26)

Backend Steps 0-14 complete. Frontend Steps 0-13 complete. Tagged `v0.2.0`.

---

## v0.4 Design Summary

### What v0.4 delivered

| Area | v0.3.1 | v0.4.0 |
|------|--------|--------|
| Data model | Topic 1↔1 Document | Topic 1→\* Work, Work 1→0..1 Document |
| Upload | Per Topic | Per Work (legacy → default Work) |
| Analysis | Per Topic | Per Work + cross-work build |
| Entities | Chunk-level atoms only | Topic-level global registry with mentions |
| Relationships | Merge outputs only | Graph snapshots with evidence edges |
| Events | Per-chunk extraction | Ordered timeline with cross-work support |
| Visualization | List/search cards | Edge table + entity registry + timeline |

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
