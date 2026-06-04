import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { listCrossWorkRuns, createCrossWorkRun, getCrossWorkRun } from "../../api/crossWork";
import { listEntities } from "../../api/crossWork";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";

interface Props {
  topicId: string;
}

export default function CrossWorkDashboard({ topicId }: Props) {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ["cross-work-runs", topicId],
    queryFn: () => listCrossWorkRuns(topicId, 5, 0),
  });

  const entitiesQuery = useQuery({
    queryKey: ["entities", topicId],
    queryFn: () => listEntities(topicId, { limit: 1 }),
  });

  // Poll active run until terminal
  const activeRunQuery = useQuery({
    queryKey: ["cross-work-run", topicId, activeRunId],
    queryFn: () => activeRunId ? getCrossWorkRun(topicId, activeRunId) : null,
    enabled: !!activeRunId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" || status === "failed" ? false : 2000;
    },
  });

  // Watch for terminal state
  useEffect(() => {
    const status = activeRunQuery.data?.status;
    if (status === "succeeded" || status === "failed") {
      setActiveRunId(null);
      queryClient.invalidateQueries({ queryKey: ["cross-work-runs", topicId] });
      queryClient.invalidateQueries({ queryKey: ["entities", topicId] });
      queryClient.invalidateQueries({ queryKey: ["graph", topicId] });
      queryClient.invalidateQueries({ queryKey: ["timeline", topicId] });
    }
  }, [activeRunQuery.data?.status, queryClient, topicId]);

  const buildMut = useMutation({
    mutationFn: () => createCrossWorkRun(topicId, { mode: "full" }),
    onSuccess: (data) => {
      setActiveRunId(data.id);
      queryClient.invalidateQueries({ queryKey: ["cross-work-runs", topicId] });
    },
  });

  const runList = runsQuery.isSuccess ? runsQuery.data : null;
  const lastRun = runList?.runs?.[0];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
        <h3 style={{ margin: 0 }}>Cross-Work Dashboard</h3>
        <button
          onClick={() => buildMut.mutate()}
          disabled={buildMut.isPending || !!activeRunId}
          style={{ fontSize: "0.8rem" }}
        >
          {buildMut.isPending || activeRunId ? "Building..." : "Run Cross-Work Build"}
        </button>
      </div>

      {buildMut.isError && (
        <ErrorBlock message={(buildMut.error as Error)?.message || "Build failed"} />
      )}

      {activeRunId && (
        <p className="text-dim" style={{ fontSize: "0.78rem", marginBottom: "0.4rem" }}>
          Build in progress... {activeRunQuery.data?.status && `(${activeRunQuery.data.status})`}
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.6rem" }}>
        <div className="card" style={{ textAlign: "center" }}>
          <p style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0 }}>
            {runList?.total ?? "—"}
          </p>
          <p className="text-dim" style={{ fontSize: "0.75rem", margin: "0.2rem 0 0 0" }}>Cross-Work Runs</p>
        </div>
        <div className="card" style={{ textAlign: "center" }}>
          <p style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0 }}>
            {entitiesQuery.isSuccess ? entitiesQuery.data.total : "—"}
          </p>
          <p className="text-dim" style={{ fontSize: "0.75rem", margin: "0.2rem 0 0 0" }}>Global Entities</p>
        </div>
      </div>

      {runsQuery.isLoading && <LoadingBlock text="Loading runs..." />}

      {lastRun && (
        <div className="card" style={{ fontSize: "0.82rem" }}>
          <h4 style={{ margin: "0 0 0.3rem 0" }}>Last Run</h4>
          <p><strong>Status:</strong> {lastRun.status} · <strong>Mode:</strong> {lastRun.mode}</p>
          {lastRun.started_at && (
            <p className="text-dim">Started: {new Date(lastRun.started_at).toLocaleString()}</p>
          )}
          {lastRun.error && (
            <p style={{ color: "#c62828", fontSize: "0.78rem" }}>Error: {lastRun.error}</p>
          )}
        </div>
      )}

      {runsQuery.isSuccess && runsQuery.data.runs.length === 0 && !buildMut.isPending && !activeRunId && (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          No cross-work runs yet. Click "Run Cross-Work Build" to analyze relationships across Works.
        </p>
      )}
    </div>
  );
}
