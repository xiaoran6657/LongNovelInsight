import type { AnalysisRunDetail } from "../../api/types";

interface Props {
  run: AnalysisRunDetail | undefined;
}

function StageBar({ label, succeeded, failed, total }: {
  label: string; succeeded: number; failed: number; total: number;
}) {
  const done = succeeded + failed;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const succW = total > 0 ? `${Math.round((succeeded / total) * 100)}%` : "0%";
  const failW = total > 0 ? `${Math.round((failed / total) * 100)}%` : "0%";

  return (
    <div style={{ marginBottom: "0.35rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "0.15rem" }}>
        <span>{label}</span>
        <span className="text-dim">{succeeded}/{total} succeeded, {failed} failed ({pct}%)</span>
      </div>
      <div style={{ height: 5, background: "#e0e0e0", borderRadius: 3, overflow: "hidden", display: "flex" }}>
        <div style={{ height: "100%", width: succW, background: "#27ae60", transition: "width 0.3s" }} />
        <div style={{ height: "100%", width: failW, background: "#e74c3c", transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

export default function AnalysisStageProgress({ run }: Props) {
  if (!run) return null;
  const r = run.run;
  const pct = r.progress_total > 0 ? Math.round((r.progress_current / r.progress_total) * 100) : 0;

  return (
    <div style={{ fontSize: "0.85rem" }}>
      {/* Overall progress */}
      <div style={{ marginBottom: "0.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
          <strong>Overall Progress</strong>
          <span className="text-dim">{r.progress_current}/{r.progress_total} ({pct}%)</span>
        </div>
        <div style={{ height: 8, background: "#e0e0e0", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: "#1976d2", transition: "width 0.3s", borderRadius: 4 }} />
        </div>
      </div>

      {/* Per-stage bars */}
      <StageBar label="Extraction" succeeded={r.extraction_succeeded} failed={r.extraction_failed} total={r.extraction_total} />
      <StageBar label="Merge" succeeded={r.merge_succeeded} failed={r.merge_failed} total={r.merge_total} />
      <StageBar
        label="Final Outputs"
        succeeded={r.final_succeeded ?? 0}
        failed={r.final_failed ?? 0}
        total={r.final_total ?? 0}
      />

      {/* Warnings */}
      {run.merge.warnings.length > 0 && (
        <details style={{ marginTop: "0.5rem", fontSize: "0.78rem" }}>
          <summary style={{ cursor: "pointer", color: "#f57f17", fontWeight: 600 }}>
            Warnings ({run.merge.warnings.length})
          </summary>
          <ul style={{ marginTop: "0.25rem", paddingLeft: "1.2rem", maxHeight: 150, overflowY: "auto" }}>
            {run.merge.warnings.map((w, i) => (
              <li key={i} style={{ marginBottom: "0.15rem" }}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      {/* Failed chunks */}
      {run.extractions.some((e) => e.status === "failed") && (
        <details style={{ marginTop: "0.5rem", fontSize: "0.78rem" }}>
          <summary style={{ cursor: "pointer", color: "#e74c3c", fontWeight: 600 }}>
            Failed Extractions ({run.extractions.filter((e) => e.status === "failed").length})
          </summary>
          <div style={{ maxHeight: 200, overflowY: "auto", marginTop: "0.25rem" }}>
            {run.extractions.filter((e) => e.status === "failed").slice(0, 20).map((e) => (
              <div key={e.id} style={{ marginBottom: "0.25rem", padding: "0.25rem", background: "#fff5f5", borderRadius: 3 }}>
                <span className="text-dim">Chunk {e.chunk_id.slice(0, 8)}… · {e.attempt_count} attempt(s)</span>
                {e.error_message && (
                  <p style={{ fontSize: "0.72rem", color: "#c62828", margin: "0.1rem 0 0 0" }}>
                    {e.error_message.length > 200 ? e.error_message.slice(0, 200) + "…" : e.error_message}
                  </p>
                )}
              </div>
            ))}
            {run.extractions.filter((e) => e.status === "failed").length > 20 && (
              <p className="text-dim" style={{ fontSize: "0.75rem" }}>
                +{run.extractions.filter((e) => e.status === "failed").length - 20} more failed extractions
              </p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
