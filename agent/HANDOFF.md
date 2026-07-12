# Current Handoff

## Objective

Complete FE-CACHE-001: centralize TanStack Query keys shared by Topic Detail and Chat, preserve
partial invalidation compatibility, prevent response-shape cache collisions, and publish the
verified increment to codex/repository-takeover.

## Status

FE-CACHE-001 completed and fully verified on 2026-07-13. The worktree started clean at commit
9f30e95. This handoff and the frontend query-key increment are the complete authorized publication
scope for the next commit on codex/repository-takeover.

## Ownership

- Primary agent: key contract, migration, unit tests, full gates, documentation, and publication.
- Query-key inventory agent: blocked by the Windows approval stream before file access.
- Query-key test agent: TanStack partial-match behavior, normalization, and isolation test matrix.

## Query-Key Contract

- Existing root strings remain stable so untouched component prefix invalidations keep working.
- Undefined and null IDs normalize to an explicit null segment.
- Topic Detail and Chat share the same topic, provider preset, effective config, and stored config
  keys.
- Chunk lists use the hierarchy chunks / Topic / list / normalized options.
- includeText, limit, and offset are canonical key fields, preventing text and summary responses
  from sharing cache entries.
- The chunks / Topic prefix invalidates every list shape for that Topic without affecting another
  Topic.
- Chat optimistic reads, writes, cancellation, rollback, and invalidation all use the identical
  session message key.

## Changes

- Add frontend/src/queryKeys.ts with small typed factories for Topic, provider/config, document,
  chapter, chunk, Work, and Chat resources used by the two pages.
- Replace every literal TanStack key in TopicDetailPage and TopicChatPage.
- Merge the prior effectiveConfig/providerPresets/provider-config-chat aliases into the same keys
  already used by Topic Detail.
- Replace chunksWithText with a response-shape-aware chunk list key.
- Add four pure tests using a real QueryClient for exact keys, option normalization, Topic prefix
  invalidation, and Chat session isolation.
- Update frontend README, project status, queue, and this handoff.

## Verification

- Frontend strict typecheck: pass.
- Expanded ESLint: pass.
- Pure-logic unit suite: 12 passed in 1.4 seconds.
- Production build: pass; 159 modules, 458.98 kB JS / 131.99 kB gzip.
- Full mocked Playwright suite: 53 passed in 18.1 seconds.
- Literal-key audit: no raw query keys remain in TopicDetailPage or TopicChatPage.
- Latest backend gate remains current from CROSS-001: Ruff pass; 755 passed, 6 deselected.
- No dependency was added and no real LLM request was made.

## Open Risks

- Query keys outside Topic Detail and Chat remain literal and can be migrated incrementally when
  their subsystems are next changed; their root shapes remain compatible with this factory.
- AnalysisRun executor ownership remains process-local.
- Deprecated v1/Job executors remain callable for v0.4 compatibility.
- scripts/integration_smoke.py remains unexecuted because it can make real LLM calls.

## Next Action

Start CHAT-002: add explicit turn/reply linkage and stable ordering for chat message pairs.