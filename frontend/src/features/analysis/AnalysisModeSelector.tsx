import type { AnalysisMode } from "../../api/types";

interface Props {
  mode: AnalysisMode;
  limitChunks: number;
  totalChunks: number;
  hasPreviousRun: boolean;
  onChangeMode: (mode: AnalysisMode) => void;
  onChangeLimitChunks: (n: number) => void;
}

const MODES: { mode: AnalysisMode; label: string; desc: string }[] = [
  { mode: "preview", label: "Preview", desc: "Analyze first N chunks. Fast and low cost." },
  { mode: "range", label: "Range", desc: "Select specific chunk or chapter indices." },
  { mode: "full", label: "Full", desc: "Analyze all chunks. May consume significant API credits." },
  { mode: "incremental", label: "Incremental", desc: "Only analyze chunks not yet processed." },
];

export default function AnalysisModeSelector({
  mode, limitChunks, totalChunks, hasPreviousRun,
  onChangeMode, onChangeLimitChunks,
}: Props) {
  return (
    <div className="card" style={{ fontSize: "0.85rem" }}>
      <h3>Analysis Mode</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {MODES.map((m) => {
          const selected = mode === m.mode;
          const disabled = m.mode === "incremental" && !hasPreviousRun;
          return (
            <label
              key={m.mode}
              style={{
                display: "flex", alignItems: "flex-start", gap: "0.5rem", cursor: disabled ? "default" : "pointer",
                padding: "0.5rem", borderRadius: 4, opacity: disabled ? 0.5 : 1,
                background: selected ? "#e3f2fd" : "#f9f9f9", border: selected ? "1px solid #1976d2" : "1px solid #e0e0e0",
              }}
            >
              <input
                type="radio" name="analysisMode" value={m.mode}
                checked={selected} disabled={disabled}
                onChange={() => onChangeMode(m.mode)}
              />
              <div>
                <div style={{ fontWeight: 600 }}>{m.label}</div>
                <div className="text-dim" style={{ fontSize: "0.78rem" }}>
                  {m.desc}
                  {disabled && " (No previous run found.)"}
                </div>
                {m.mode === "full" && selected && (
                  <div style={{ color: "#e65100", fontSize: "0.78rem", marginTop: "0.25rem", fontWeight: 600 }}>
                    This will process ALL {totalChunks} chunks and may consume significant API credits.
                  </div>
                )}
              </div>
            </label>
          );
        })}
      </div>

      {mode === "preview" && (
        <div style={{ marginTop: "0.75rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            Limit chunks:
            <input type="number" min={1} max={totalChunks || 1000} value={limitChunks}
              onChange={(e) => onChangeLimitChunks(Math.max(1, Number(e.target.value)))}
              style={{ width: 70 }} />
            {totalChunks > 0 && <span className="text-dim">of {totalChunks} total</span>}
          </label>
        </div>
      )}
    </div>
  );
}
