# LongNovelInsight — Roadmap

## v0.1.x — MVP & Release Baseline

Status: Complete.

- Local-first localhost workflow.
- Provider configuration.
- One Topic = one TXT novel.
- Parse chapters/chunks.
- Six structured analysis types.
- Evidence-grounded chat.
- Local SQLite/data storage.
- Smoke tests and release docs.

## v0.2.x — Scale & Depth for Single TXT

Goal: make full-length TXT novels analyzable with lower repeated token cost and deeper structured outputs.

- Chunk-level local extraction.
- Global merge pipeline.
- Stable entity/event IDs.
- Async run-first analysis.
- Preview/range/full/incremental modes.
- Run history and per-chunk progress.
- Output versioning.
- Disk/hybrid artifact storage.
- Timeline, character arcs, worldbuilding, foreshadowing.
- Frontend analysis UX refactor.
- Playwright e2e tests.

Non-goals:
- EPUB/PDF.
- Multi-book Topic.
- Vector database.
- Graph visualization.

## v0.3.x — Source Formats & Retrieval

Status: Backend complete (Steps 1-12). Frontend pending (12 steps).

- EPUB parsing and metadata extraction.
- Unified TXT/EPUB source abstraction.
- SQLite FTS5 full-text search.
- Hybrid retrieval (FTS + keyword + structured + analysis output).
- Retrieval trace/debugging.
- Similar scenes.
- Entity/evidence explorer.
- Optional embedding rerank (skeleton, disabled by default).

Non-goals:
- Cross-book analysis.
- Interactive graph visualization.
- Cloud sync.

## v0.4.x — Multi-Book & Visualization

Goal: support novel series and visual analysis.

- One Topic contains multiple Works.
- Cross-work entity registry.
- Cross-work relationship matching.
- Cross-work timeline.
- Character relationship network.
- Event timeline visualization.
- Causal chain diagram.
- Evidence-linked graph nodes/edges.

Non-goals:
- Plugin marketplace.
- SaaS account system.
- Remote storage.

## v0.5.x — Open Source Productization

Goal: make the project easy to install, maintain, migrate, export, debug, and contribute to.

- Setup scripts and doctor command.
- Backup/restore/import/export.
- Data integrity check.
- Benchmark/evaluation harness.
- Local diagnostics and logs.
- Prompt pack / provider adapter / analysis recipe extension points.
- CONTRIBUTING / SECURITY / PRIVACY docs.
- Release checklist.