# LongNovelInsight v0.2 — Benchmarks & Cost Guide

## Pipeline Comparison: v0.1 vs v0.2

| Metric | v0.1 (direct 6-type) | v0.2 (staged pipeline) |
|--------|---------------------|------------------------|
| LLM calls per chunk | 6 (one per analysis type) | 1 (local_extraction only) |
| Merge cost | N/A (batch-map-merge within v0.1) | 0 (deterministic Python, no LLM) |
| Final output cost | N/A | 0 (deterministic Python, no LLM) |
| Prompt tokens per chunk | ~6 × 800 = ~4,800 | ~1 × 800 = ~800 |
| Completion tokens per chunk | ~6 × 1,024 = ~6,144 | ~1 × 2,048 = ~2,048 |
| **Total tokens per chunk** | **~10,944** | **~2,848** |
| **Cost per 100 chunks** | ~1.1M tokens | ~285K tokens |

v0.2 is ~4× more token-efficient per chunk because each chunk is sent to the LLM
only once (for local_extraction), rather than 6 times (once per analysis type).

## Analysis Modes

| Mode | Chunks Selected | Token Est. (100-chunk novel) | Use Case |
|------|----------------|-----------------------------|----------|
| **preview** | 3–5 (auto) | ~14K | Quick skim, small cost |
| **preview** (limit=10) | 10 | ~28K | More thorough preview |
| **range** (by chapter) | varies | varies | Focus on specific chapters |
| **full** | all | ~285K (100 chunks) | Complete novel analysis |
| **incremental** | remaining only | partial | Continue from previous run |

## Size Recommendations

| Novel Size | Chunks (est.) | Recommended Mode | Parallelism |
|------------|--------------|------------------|-------------|
| < 50K chars (small) | < 20 | full | 6 |
| 50K–300K chars (medium) | 20–100 | preview first, then full | 6 |
| 300K–1M chars (large) | 100–300 | preview → range → full | 3–4 |
| > 1M chars (huge) | > 300 | preview → incremental batches | 1–3 |

## Concurrency & Parallelism

- **analysis_parallelism** config: 1–6 (clamped)
- Default: 3
- Recommended:
  - Small/medium text: 6 (parallelism limited by chunk count)
  - Large text: 3 (balance speed and API rate limits)
  - Huge text: 1–2 (avoid rate limiting; use incremental)

## Real LLM Benchmark Log Template

| Date | Provider | Model | Novel Chars | Chunks | Mode | Extraction Time | Total Tokens | Cost (est.) | Notes |
|------|----------|-------|------------|--------|------|----------------|-------------|-------------|-------|
| YYYY-MM-DD | deepseek-chat | v4-flash | 50,000 | 15 | preview (lim=5) | 12s | 14,200 | $0.001 | — |
| | | | | | | | | | |

Fill in rows as you run real analyses. This helps track costs and
choose the right mode for future runs.

## v0.2 Pipeline Stage Timings

After each run, `metadata_json.stage_timings` records:

```json
{
  "stage_timings": {
    "extraction": 12.3,
    "merge": 1.2,
    "final": 0.8
  },
  "usage_by_stage": {
    "extraction": 14200,
    "merge": 0,
    "final": 0
  }
}
```

- **extraction** is the dominant cost (LLM calls)
- **merge** and **final** are pure Python (near-zero cost, no API usage)
- Compare timings across runs to identify slow chunks or provider latency issues
