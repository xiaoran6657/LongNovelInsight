import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAnalysisRun, deleteAnalysisOutputs, listAnalysisOutputsV2 } from "../../api/analysis";
import type { AnalysisOutput } from "../../api/types";
import { ApiError } from "../../api/client";
import AnalysisOutputCard from "../../components/AnalysisOutputCard";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";
import EmptyState from "../../components/EmptyState";

const ALL_TYPES = ["overview", "characters", "relations", "events", "causality", "themes"];

function groupLatest(outputs: AnalysisOutput[]): AnalysisOutput[] {
  const grouped: Record<string, AnalysisOutput[]> = {};
  for (const o of outputs) {
    if (!grouped[o.output_type]) grouped[o.output_type] = [];
    grouped[o.output_type].push(o);
  }
  const latest: AnalysisOutput[] = [];
  for (const items of Object.values(grouped)) {
    items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    latest.push(items[0]);
  }
  latest.sort((a, b) => a.output_type.localeCompare(b.output_type));
  return latest;
}

interface Props {
  topicId: string;
  runId: string | null;
}

export default function AnalysisOutputsPanel({ topicId, runId }: Props) {
  const qc = useQueryClient();
  const [outputTypeFilter, setOutputTypeFilter] = useState("");

  // Check if selected run is still active
  const { data: runDetail } = useQuery({
    queryKey: ["analysisRun", runId],
    queryFn: () => getAnalysisRun(runId!),
    enabled: !!runId,
  });
  const isRunActive = runDetail?.run.status === "pending" || runDetail?.run.status === "running";

  // Refetch outputs when a selected run transitions from active to terminal
  const wasActiveRef = useRef(false);
  useEffect(() => {
    if (isRunActive) {
      wasActiveRef.current = true;
    } else if (wasActiveRef.current && runDetail) {
      wasActiveRef.current = false;
      qc.invalidateQueries({ queryKey: ["outputs", topicId, runId] });
    }
  }, [isRunActive, runDetail, qc, topicId, runId]);

  // Fetch outputs filtered by run if runId is set, otherwise latest only
  const { data: outputsData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["outputs", topicId, runId],
    queryFn: () => runId
      ? listAnalysisOutputsV2(topicId, { runId })
      : listAnalysisOutputsV2(topicId, { latestOnly: true }),
    enabled: !!topicId,
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteAnalysisOutputs(topicId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
      qc.invalidateQueries({ queryKey: ["topic", topicId] });
    },
  });

  const allOutputs = outputsData?.outputs ?? [];
  const latest = groupLatest(allOutputs);
  const filtered = outputTypeFilter
    ? allOutputs.filter((o) => o.output_type === outputTypeFilter)
    : latest;

  const missingTypes = ALL_TYPES.filter(
    (t) => !allOutputs.some((o) => o.output_type === t)
  );

  if (isLoading) return <LoadingBlock text="Loading outputs..." />;
  if (isError) {
    const apiErr = error instanceof ApiError ? error : undefined;
    return (
      <div>
        <h2>{runId ? "Run Outputs" : "Outputs"}</h2>
        <ErrorBlock
          title="Failed to load analysis outputs"
          message={apiErr?.detail ?? error?.message ?? "Unable to fetch outputs."}
          status={apiErr?.status}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div>
      <h2>{runId ? "Run Outputs" : "Outputs"}</h2>

      {isRunActive && runId && (
        <p className="text-dim" style={{ fontSize: "0.82rem", marginBottom: "0.5rem" }}>
          Analysis is still running. Outputs will appear when the final stage completes.
        </p>
      )}

      {allOutputs.length === 0 && !isRunActive && (
        <EmptyState
          title={runId ? "No outputs for this run yet" : "No analysis outputs yet"}
          description={runId ? "The run hasn't produced any outputs." : "Run an analysis to see results here."}
        />
      )}

      {missingTypes.length > 0 && missingTypes.length < ALL_TYPES.length && allOutputs.length > 0 && (
        <div className="card" style={{ background: "#fff3e0", fontSize: "0.82rem", marginBottom: "0.5rem" }}>
          <strong>Missing types:</strong>{" "}
          {missingTypes.map((t) => (
            <span key={t} style={{ marginRight: "0.5rem", color: "#e65100" }}>{t}</span>
          ))}
        </div>
      )}

      {allOutputs.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <span>
              <strong>{allOutputs.length}</strong> output(s)
              {runId && <span className="text-dim" style={{ fontSize: "0.78rem", marginLeft: "0.5rem" }}>from this run</span>}
            </span>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <select value={outputTypeFilter} onChange={(e) => setOutputTypeFilter(e.target.value)}
                style={{ fontSize: "0.8rem" }}>
                <option value="">All types</option>
                {ALL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              {!runId && (
                <button
                  onClick={() => { if (confirm("Delete ALL analysis outputs for this topic?")) deleteMut.mutate(); }}
                  disabled={deleteMut.isPending}
                  style={{ fontSize: "0.75rem", background: "#e74c3c" }}
                  aria-label="Delete all analysis outputs">
                  Delete All
                </button>
              )}
            </div>
          </div>

          {filtered.map((o) => (
            <div key={o.id} style={{ marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                <div>
                  <strong>{o.output_type}</strong>
                  {o.run_id && (
                    <span className="text-dim" style={{ fontSize: "0.72rem", marginLeft: "0.5rem" }}>
                      run {o.run_id.slice(0, 8)}…
                    </span>
                  )}
                </div>
                <span className="text-dim" style={{ fontSize: "0.72rem" }}>
                  {new Date(o.created_at).toLocaleDateString()}
                </span>
              </div>
              <AnalysisOutputCard output={o} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
