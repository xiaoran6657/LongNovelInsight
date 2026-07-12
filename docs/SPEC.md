# LongNovelInsight v0.4.0-dev — Product Specification

## Product Goal

LongNovelInsight is a local-first desktop-web workspace for readers, researchers, and authors
who need evidence-grounded analysis of long novels and multi-volume story universes. It uses a
user-configured OpenAI-compatible model while keeping source text, analysis results, and API
credentials on the local machine.

## Core User Flow

1. Configure an LLM provider and model.
2. Create a Topic representing one story universe or research workspace.
3. Add one or more Works, such as novels or volumes.
4. Upload one TXT or EPUB source document to each Work.
5. Parse the source into chapters and chunks with source locators.
6. Run preview, range, full, or incremental evidence-grounded analysis.
7. Inspect outputs, search/retrieve source evidence, and chat with citations to local chunks.
8. Build deterministic cross-work entities, relationship graphs, and timelines.

## Current Capabilities

- Provider presets and direct OpenAI-compatible API configuration.
- TXT encoding normalization for UTF-8, GBK/GB18030, and UTF-16 families.
- EPUB container, metadata, spine, XHTML, and source-locator parsing.
- Six structured output families: overview, characters, relations, events, causality, themes.
- Staged local extraction, deterministic merge, final output generation, retry, resume, cancel,
  token accounting, and hybrid artifact storage.
- SQLite FTS5, CJK fallback, structured retrieval, retrieval traces, entity evidence, and similar
  scenes; optional semantic rerank remains disabled by default.
- Evidence-grounded chat with structured evidence records.
- Topic-to-many-Work organization, with at most one Document per Work.
- Deterministic cross-work entity registry, relationship graph snapshot, and event timeline.

## Data and Privacy Contract

- The application is single-user and local-only.
- Uploaded sources and generated artifacts are stored under the local `data/` directory.
- API keys are stored only in the local SQLite database and are masked in API responses.
- Routine tests must not use the real data directory, real database, or real LLM calls.
- The repository must never contain uploaded novels, API keys, local databases, or generated
  analysis output.

## v0.4 Acceptance Criteria

- A Topic can contain multiple independently managed Works.
- A Work cannot contain more than one source Document.
- TXT and EPUB upload, parsing, deletion, and re-upload preserve Work isolation.
- Analysis results and source evidence remain scoped to the correct Topic and Work.
- Cross-work entities, graph edges, and timeline items link back to source evidence.
- Legacy Topic-level endpoints remain compatible through default Work resolution.
- Backend tests and Ruff pass in the declared environment.
- Frontend typecheck, lint, build, and relevant Playwright workflows pass.
- No default workflow makes a real LLM request without a visible user action.

## Explicit Non-Goals for v0.4

- Authentication, multi-user accounts, SaaS, cloud sync, or remote storage.
- Multiple source documents per Work.
- PDF, OCR, or DRM removal.
- Docker, external databases, task queues, vector databases, or graph databases.
- LLM orchestration frameworks or plugin systems.
- Automatic LLM-based cross-work entity resolution.
- Mobile-first UI or public internet deployment.

## Known Product Gaps

- Character graph is an edge-table MVP rather than an interactive visualization.
- Timeline pagination and evidence expansion are limited.
- Work selection is not yet wired consistently to every cross-work frontend tab.
- Work-level analysis lacks complete cost confirmation, run handoff, and result tracking.
- Analysis output rendering needs stronger normalization for malformed model JSON.
- Process restart recovery for in-process background analysis requires hardening.
