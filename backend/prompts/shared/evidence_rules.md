# Evidence Rules (shared by all analysis prompts)

Every extracted item must include at least one evidence quote in evidence_quotes.
Each evidence quote must be copied exactly from the provided source text — do not paraphrase, summarize, or rewrite.
Do not quote text that is not present in the input chunks.
Each source_chunk_ids entry must be one of the chunk IDs provided in the input.
Prefer short quotes (under 300 characters). Do not copy entire passages.
Bind evidence_quotes and source_chunk_ids to the specific item they support, not only at the top level.
If no direct textual evidence exists for an item, omit the item entirely.
Do not include items solely based on general knowledge or genre expectations.
