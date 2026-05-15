# Merge Prompt Conventions

This document describes the shared conventions for all merge prompts in this directory. Each specific merge prompt (merge_characters.md, merge_events.md, etc.) inherits these rules.

## General Merge Principles

1. **Deduplicate, don't delete.** When merging, combine evidence and IDs from all sources. Never discard an item just because it appears in only one source.
2. **Resolve conflicts conservatively.** When two sources disagree, preserve both perspectives and lower confidence. Do not pick one side and discard the other.
3. **Track provenance.** Every merged item should include all source_chunk_ids from its constituent parts.
4. **Confidence reflects consensus.** High confidence = multiple independent extractions agree. Low confidence = single source or disagreement.
5. **Canonicalize IDs.** The merge phase produces stable final IDs. Map all local *_hint fields to canonical slugs.
6. **Preserve uncertainty.** If the merge is ambiguous, note it rather than forcing a resolution.
