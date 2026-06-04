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

  // Auto-detect running run on mount
  const detectedRunningId =
    runsQuery.isSuccess && runsQuery.data.runs.length > 0 &&
    (runsQuery.data.runs[0].status === "pending" || runsQuery.data.runs[0].status === "running")
      ? runsQuery.data.runs[0].id : null;

  const pollId = activeRunId || detectedRunningId;

  // Poll active run until terminal
  const activeRunQuery = useQuery({
    queryKey: ["cross-work-run", topicId, pollId],
    queryFn: () => pollId ? getCrossWorkRun(topicId, pollId) : null,
    enabled: !!pollId,
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

  // Fetch last run detail separately for warnings (list API doesn't return warnings)
  const lastRunDetailQuery = useQuery({
    queryKey: ["cross-work-run", topicId, lastRun?.id],
    queryFn: () => lastRun ? getCrossWorkRun(topicId, lastRun.id) : null,
    enabled: !!lastRun && !pollId,
  });

  const runWarnings: string[] =
    activeRunQuery.data?.warnings ?? lastRunDetailQuery.data?.warnings ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
        <h3 style={{ margin: 0 }}>Cross-Work Dashboard</h3>
        <button
          onClick={() => buildMut.mutate()}
          disabled={buildMut.isPending || !!pollId}
          style={{ fontSize: "0.8rem" }}
        >
          {buildMut.isPending || pollId ? "Building..." : "Run Cross-Work Build"}
        </button>
      </div>

      {buildMut.isError && (
        <ErrorBlock message={(buildMut.error as Error)?.message || "Build failed"} />
      )}

      {pollId && (
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

      {/* Warnings */}
      {runWarnings.length > 0 && (
        <div className="card" style={{ background: "#fff8e1", marginBottom: "0.6rem", fontSize: "0.78rem" }}>
          <strong>Warnings ({runWarnings.length}):</strong>
          {runWarnings.slice(0, 3).map((w: string, i: number) => (
            <p key={i} className="text-dim" style={{ margin: "0.15rem 0", fontSize: "0.75rem" }}>{w}</p>
          ))}
          {runWarnings.length > 3 && (
            <p className="text-dim" style={{ fontSize: "0.72rem" }}>+{runWarnings.length - 3} more</p>
          )}
        </div>
      )}

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

      {runsQuery.isSuccess && runsQuery.data.runs.length === 0 && !buildMut.isPending && !pollId && (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          No cross-work runs yet. Click "Run Cross-Work Build" to analyze relationships across Works.
        </p>
      )}
    </div>
  );
}
