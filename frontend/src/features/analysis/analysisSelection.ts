import type { ChunkRange } from "./ChunkRangeSelector";
import type { ChunksMetaResponse } from "../../api/types";

export function estimateTokens(
  meta: ChunksMetaResponse | undefined,
  mode: string,
  limitChunks: number,
  range: ChunkRange
): {
  selectedChunks: number;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  note: string;
} {
  const totalChunks = meta?.chunk_count ?? 0;
  const totalChars = meta?.total_chars ?? 0;
  const charsPerChunk = totalChunks > 0 ? Math.round(totalChars / totalChunks) : 2000;
  const tokensPerChunk = Math.round(charsPerChunk / 1.5);

  let selected = 0;
  const noteParts: string[] = [];

  if (mode === "preview") {
    selected = Math.min(limitChunks, totalChunks || limitChunks);
    noteParts.push(`preview: first ${selected} of ${totalChunks} chunks`);
  } else if (mode === "range") {
    if (range.start != null && range.end != null && range.start <= range.end) {
      if (range.mode === "chapter" && meta) {
        selected = 0;
        for (const ch of meta.chunks_by_chapter) {
          if (ch.chapter_index >= range.start && ch.chapter_index <= range.end) {
            selected += ch.chunk_count;
          }
        }
        noteParts.push(`chapter range ${range.start}–${range.end}: ${selected} chunks across chapters`);
      } else {
        selected = range.end - range.start + 1;
        selected = Math.min(selected, totalChunks);
        noteParts.push(`chunk range: chunks ${range.start}–${range.end}, ${selected} chunks`);
      }
    } else {
      selected = 0;
      noteParts.push("invalid range");
    }
  } else if (mode === "full") {
    selected = totalChunks;
    noteParts.push(`full: all ${totalChunks} chunks`);
  } else if (mode === "incremental") {
    selected = totalChunks > 0 ? Math.ceil(totalChunks * 0.3) : 0;
    noteParts.push("incremental: remaining chunks only (estimate)");
  }

  const typeCount = 6;
  const extractionInput = selected * (tokensPerChunk + 600);
  const extractionOutput = selected * 2048;
  const total = extractionInput + extractionOutput;

  return {
    selectedChunks: selected,
    estimatedInputTokens: extractionInput,
    estimatedOutputTokens: extractionOutput,
    note: [
      `v2 staged pipeline: ~${selected} chunks × 1 extraction each`,
      `v0.1 would use ~${selected * typeCount} LLM calls; v0.2 uses ~${selected}`,
      `~${tokensPerChunk.toLocaleString()} tokens/chunk`,
      `Estimated total: ${total.toLocaleString()} tokens (input: ${extractionInput.toLocaleString()}, output: ${extractionOutput.toLocaleString()})`,
    ].join(". "),
  };
}

export function isRangeValid(range: ChunkRange): boolean {
  if (range.start == null || range.end == null) return true;
  return range.start <= range.end;
}
