import { expect, test } from "@playwright/test";

import {
  estimateTokens,
  isRangeValid,
} from "../src/features/analysis/analysisSelection";
import type { ChunksMetaResponse } from "../src/api/types";

const meta: ChunksMetaResponse = {
  topic_id: "topic-1",
  document_id: "document-1",
  chunk_count: 10,
  total_chars: 15000,
  estimated_tokens: 10000,
  chapter_count: 3,
  first_chunk_index: 0,
  last_chunk_index: 9,
  first_global_chunk_index: 0,
  last_global_chunk_index: 9,
  chunks_by_chapter: [
    {
      chapter_index: 0,
      title: "One",
      chunk_count: 2,
      char_count: 3000,
      estimated_tokens: 2000,
    },
    {
      chapter_index: 1,
      title: "Two",
      chunk_count: 3,
      char_count: 4500,
      estimated_tokens: 3000,
    },
    {
      chapter_index: 2,
      title: "Three",
      chunk_count: 5,
      char_count: 7500,
      estimated_tokens: 5000,
    },
  ],
};

test("preview clamps selection and applies preview retry buffer", () => {
  const estimate = estimateTokens({
    meta,
    mode: "preview",
    limitChunks: 3,
    range: { mode: "chunk", start: null, end: null },
  });

  expect(estimate.selectedChunks).toBe(3);
  expect(estimate.estimatedInputTokens).toBe(7200);
  expect(estimate.estimatedOutputTokens).toBe(9188);
  expect(estimate.note).toContain("preview: first 3 of 10 chunks");
  expect(estimate.note).toContain("× 1.15 retry buffer");
});

test("chapter and chunk ranges calculate inclusive bounded selections", () => {
  const chapters = estimateTokens({
    meta,
    mode: "range",
    limitChunks: 5,
    range: { mode: "chapter", start: 0, end: 1 },
  });
  const chunks = estimateTokens({
    meta,
    mode: "range",
    limitChunks: 5,
    range: { mode: "chunk", start: 2, end: 20 },
  });

  expect(chapters.selectedChunks).toBe(5);
  expect(chapters.note).toContain("5 chunks across chapters");
  expect(chunks.selectedChunks).toBe(10);
});

test("full and incremental modes derive selection from metadata", () => {
  const full = estimateTokens({
    meta,
    mode: "full",
    limitChunks: 5,
    range: { mode: "chunk", start: null, end: null },
  });
  const incremental = estimateTokens({
    meta,
    mode: "incremental",
    limitChunks: 5,
    range: { mode: "chunk", start: null, end: null },
  });

  expect(full.selectedChunks).toBe(10);
  expect(full.note).toContain("× 1.25 retry buffer");
  expect(incremental.selectedChunks).toBe(3);
  expect(incremental.note).toContain("× 1.15 retry buffer");
});

test("thinking mode inflates output and output tokens are capped", () => {
  const estimate = estimateTokens({
    meta,
    mode: "preview",
    limitChunks: 2,
    range: { mode: "chunk", start: null, end: null },
    effectiveConfig: {
      model_name: "test",
      temperature: 0.1,
      max_output_tokens: 1000,
      thinking_mode: "enabled",
      analysis_parallelism: 1,
      supports_json_output: true,
      supports_thinking: true,
      is_ready: true,
      missing_fields: [],
      warnings: [],
    },
  });
  const capped = estimateTokens({
    meta,
    mode: "preview",
    limitChunks: 1,
    range: { mode: "chunk", start: null, end: null },
    effectiveConfig: {
      model_name: "test",
      temperature: 0.1,
      max_output_tokens: 99999,
      thinking_mode: "disabled",
      analysis_parallelism: 1,
      supports_json_output: true,
      supports_thinking: true,
      is_ready: true,
      missing_fields: [],
      warnings: [],
    },
  });

  expect(estimate.estimatedOutputTokens).toBe(2093);
  expect(estimate.note).toContain("thinking mode enabled");
  expect(capped.note).toContain("~10650 tokens/chunk");
});

test("range validation accepts partial input and rejects negative or reversed bounds", () => {
  expect(isRangeValid({ mode: "chunk", start: null, end: null })).toBe(true);
  expect(isRangeValid({ mode: "chunk", start: 1, end: null })).toBe(true);
  expect(isRangeValid({ mode: "chunk", start: 1, end: 2 })).toBe(true);
  expect(isRangeValid({ mode: "chunk", start: 2, end: 1 })).toBe(false);
  expect(isRangeValid({ mode: "chunk", start: -1, end: 2 })).toBe(false);
});