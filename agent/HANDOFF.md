# Current Handoff

## Objective

Restore active maintenance, replace the legacy Claude-specific workflow with Codex-led
project governance, clean generated and historical agent artifacts, and establish a verified
quality baseline for v0.4.0-dev.

## Status

`TAKEOVER-001` is verified on 2026-07-12 on branch `codex/repository-takeover`. Governance
migration, version alignment, generated artifact cleanup, dependency security updates, and all
default quality gates are complete. Backend: 725 passed and 6 integration tests deselected.
Frontend: typecheck, lint, build, and 44 Playwright tests passed; npm audit reports 0.
The user authorized staging, commit, and push for this task. Tags and releases are not authorized.

## Ownership

- Primary agent: repository governance, cleanup, integration, and final verification.
- Backend audit agent: backend tests, Ruff, and code-risk report.
- Frontend audit agent: typecheck, lint, build, E2E inventory, and frontend-risk report.
- Governance audit agent: legacy workflow and documentation migration review.

## Current Changes

- Replaced the root agent rules with a Codex-led, versioned source-of-truth model.
- Rewrote the development workflow for multi-agent, cross-session delivery.
- Added durable agent coordination and handoff documentation.
- Unified v0.4 version metadata across backend runtime, package metadata, health API, frontend,
  tests, and visible UI.
- Removed legacy Claude configuration, runner outputs, historical development Prompts, caches,
  build outputs, and obsolete local sample text files without touching `data/`.
- Removed import-time data-directory creation and isolated test database/data paths.
- Replaced exception-swallowing column migrations with explicit schema inspection.
- Fixed Topic, Document, and Chat deletion under real foreign-key enforcement.
- Normalized EPUB MIME metadata to `application/epub+zip`.

## Next Action

Publish the verified takeover commit, then start `UI-001`: connect active Work filtering to
Entities, Graph, and Timeline. Keep release tagging separate until the remaining v0.4 correctness
tasks and release notes are reviewed.
