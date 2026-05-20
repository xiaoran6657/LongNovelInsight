import { useState } from "react";
import type { ChunksMetaResponse } from "../../api/types";

export interface ChunkRange {
  mode: "chunk" | "chapter";
  start: number | null;
  end: number | null;
}

interface Props {
  meta: ChunksMetaResponse | undefined;
  value: ChunkRange;
  onChange: (range: ChunkRange) => void;
}

export default function ChunkRangeSelector({ meta, value, onChange }: Props) {
  const [mode, setMode] = useState<"chunk" | "chapter">(value.mode);
  const maxChunk = meta ? meta.last_chunk_index ?? meta.chunk_count - 1 : 0;
  const maxChapter = meta ? meta.chapter_count - 1 : 0;

  function update(m: "chunk" | "chapter", start: number | null, end: number | null) {
    setMode(m);
    onChange({ mode: m, start, end });
  }

  function clearSelection() {
    setMode("chunk");
    onChange({ mode: "chunk", start: null, end: null });
  }

  const hasSelection = value.start != null || value.end != null;

  return (
    <div className="card" style={{ fontSize: "0.85rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <h3 style={{ margin: 0 }}>Range Selection</h3>
        {hasSelection && (
          <button onClick={clearSelection} style={{ fontSize: "0.75rem", padding: "0.1em 0.5em" }}>
            Clear
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "0.5rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
          <input type="radio" name="rangeMode" checked={mode === "chunk"} onChange={() => update("chunk", value.start, value.end)} />
          By chunk index
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
          <input type="radio" name="rangeMode" checked={mode === "chapter"} onChange={() => update("chapter", value.start, value.end)} />
          By chapter index
        </label>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          {mode === "chunk" ? "Chunk" : "Chapter"} start:
          <input
            type="number"
            min={0}
            max={mode === "chunk" ? maxChunk : maxChapter}
            value={value.start ?? ""}
            onChange={(e) => {
              const v = e.target.value ? Number(e.target.value) : null;
              update(mode, v, value.end);
            }}
            style={{ width: 70 }}
            placeholder="0"
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          end:
          <input
            type="number"
            min={0}
            max={mode === "chunk" ? maxChunk : maxChapter}
            value={value.end ?? ""}
            onChange={(e) => {
              const v = e.target.value ? Number(e.target.value) : null;
              update(mode, value.start, v);
            }}
            style={{ width: 70 }}
            placeholder={String(mode === "chunk" ? maxChunk : maxChapter)}
          />
        </label>
      </div>

      {value.start != null && value.end != null && value.start > value.end && (
        <p className="field-error" style={{ marginTop: "0.25rem" }}>Start must be ≤ end.</p>
      )}
      {meta && (
        <p className="text-dim" style={{ fontSize: "0.75rem", marginTop: "0.5rem" }}>
          Available: {mode === "chunk" ? `chunks 0–${maxChunk}` : `chapters 0–${maxChapter}`}
          {hasSelection && value.start != null && value.end != null && value.start <= value.end && (
            <> — {value.end - value.start + 1} {mode === "chunk" ? "chunks" : "chapters"} selected</>
          )}
        </p>
      )}
    </div>
  );
}

export function rangeToSelectionParams(range: ChunkRange) {
  if (range.start == null && range.end == null) return {};
  if (range.mode === "chunk") {
    return {
      chunk_index_start: range.start ?? undefined,
      chunk_index_end: range.end ?? undefined,
    };
  }
  return {
    chapter_index_start: range.start ?? undefined,
    chapter_index_end: range.end ?? undefined,
  };
}
