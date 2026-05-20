import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listAnalysisRuns, retryFailedAnalysisRun, resumeAnalysisRun } from "../../api/analysis";
import type { AnalysisRunListItem } from "../../api/types";
import LoadingBlock from "../../components/LoadingBlock";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function fmtTokens(n: number): string {
  if (!n) return "—";
  return n.toLocaleString();
}

function statusColor(s: string): string {
  switch (s) {
    case "succeeded": return "#27ae60";
    case "partial_success": return "#f57f17";
    case "failed": return "#e74c3c";
    case "cancelled": return "#999";
    case "running": return "#1976d2";
    default: return "#999";
  }
}

interface Props {
  topicId: string;
  activeRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

export default function AnalysisRunHistory({ topicId, activeRunId, onSelectRun }: Props) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["analysisRuns", topicId],
    queryFn: () => listAnalysisRuns(topicId),
    enabled: !!topicId,
  });

  const runs = data?.runs ?? [];

  const retryMut = useMutation({
    mutationFn: (runId: string) => retryFailedAnalysisRun(runId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["analysisRun"] });
    },
  });

  const resumeMut = useMutation({
    mutationFn: (runId: string) => resumeAnalysisRun(runId, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["analysisRun"] });
    },
  });

  if (isLoading) return <LoadingBlock text="Loading run history..." />;
  if (runs.length === 0) return null;

  return (
    <div className="card" style={{ fontSize: "0.85rem" }}>
      <h3>Run History ({runs.length})</h3>
      <div style={{ maxHeight: 400, overflowY: "auto" }}>
        {runs.map((r) => (
          <RunRow
            key={r.id}
            run={r}
            isActive={r.id === activeRunId}
            onSelect={() => onSelectRun(r.id === activeRunId ? null : r.id)}
            onRetry={() => retryMut.mutate(r.id)}
            onResume={() => resumeMut.mutate(r.id)}
            retrying={retryMut.isPending}
            resuming={resumeMut.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function RunRow({
  run, isActive, onSelect, onRetry, onResume, retrying, resuming,
}: {
  run: AnalysisRunListItem;
  isActive: boolean;
  onSelect: () => void;
  onRetry: () => void;
  onResume: () => void;
  retrying: boolean;
  resuming: boolean;
}) {
  const canRetry = run.status === "partial_success" || run.status === "failed";
  const canResume = run.status === "partial_success" || run.status === "failed";

  return (
    <div
      onClick={onSelect}
      style={{
        padding: "0.5rem", marginBottom: "0.35rem", cursor: "pointer",
        background: isActive ? "#e3f2fd" : "#f9f9f9",
        border: isActive ? "1px solid #1976d2" : "1px solid #e0e0e0",
        borderRadius: 4,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.25rem" }}>
        <span>
          <strong>{run.mode}</strong>{" "}
          <span style={{ color: statusColor(run.status), fontWeight: 600 }}>{run.status}</span>
        </span>
        <span className="text-dim" style={{ fontSize: "0.75rem" }}>
          {fmtDate(run.created_at)}
        </span>
      </div>
      <div className="text-dim" style={{ fontSize: "0.75rem", marginTop: "0.15rem" }}>
        Extraction: {run.extraction_succeeded}/{run.extraction_failed} · Merge: {run.merge_succeeded}/{run.merge_failed} · Tokens: {fmtTokens(run.total_tokens)}
        {run.model_used && <> · {run.model_used}</>}
      </div>
      <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.35rem" }}>
        {canRetry && (
          <button onClick={(e) => { e.stopPropagation(); onRetry(); }} disabled={retrying}
            style={{ fontSize: "0.72rem", padding: "0.15em 0.5em" }}>
            {retrying ? "Retrying..." : "Retry Failed"}
          </button>
        )}
        {canResume && (
          <button onClick={(e) => { e.stopPropagation(); onResume(); }} disabled={resuming}
            style={{ fontSize: "0.72rem", padding: "0.15em 0.5em" }}>
            {resuming ? "Resuming..." : "Resume"}
          </button>
        )}
      </div>
    </div>
  );
}
