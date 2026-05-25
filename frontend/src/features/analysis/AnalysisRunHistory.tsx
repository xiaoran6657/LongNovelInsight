import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listAnalysisRuns, retryFailedAnalysisRun, resumeAnalysisRun } from "../../api/analysis";
import type { AnalysisRunListItem } from "../../api/types";
import { ApiError } from "../../api/client";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function fmtTokens(n: number): string {
  if (!n) return "—";
  return n.toLocaleString();
}

function statusTone(s: string): "ok" | "warn" | "error" | "neutral" {
  switch (s) {
    case "succeeded": return "ok";
    case "partial_success": return "warn";
    case "failed": return "error";
    default: return "neutral";
  }
}

const PAGE_SIZE = 20;

interface Props {
  topicId: string;
  activeRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

export default function AnalysisRunHistory({ topicId, activeRunId, onSelectRun }: Props) {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [allRuns, setAllRuns] = useState<AnalysisRunListItem[]>([]);
  const prevTopicRef = useRef(topicId);

  // Reset accumulated state when topic changes
  if (prevTopicRef.current !== topicId) {
    prevTopicRef.current = topicId;
    if (page !== 0) setPage(0);
    if (allRuns.length > 0) setAllRuns([]);
  }

  const offset = page * PAGE_SIZE;

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["analysisRuns", topicId, { offset }],
    queryFn: () => listAnalysisRuns(topicId, { limit: PAGE_SIZE, offset }),
    enabled: !!topicId,
    placeholderData: (prev) => prev,
  });

  // Accumulate runs: page 0 replaces, page > 0 appends (deduplicating by id)
  const dataRef = useRef<typeof data>(undefined);
  useEffect(() => {
    if (!data || data === dataRef.current) return;
    dataRef.current = data;
    const runs = data.runs ?? [];
    if (offset === 0) {
      setAllRuns(runs);
    } else {
      setAllRuns((prev) => {
        const existingIds = new Set(prev.map((r) => r.id));
        const newOnes = runs.filter((r) => !existingIds.has(r.id));
        return newOnes.length > 0 ? [...prev, ...newOnes] : prev;
      });
    }
  }, [data, offset]);

  // When external code invalidates analysisRuns (e.g. after creating a new run),
  // a refetch on offset > 0 won't show the new item. Detect this and reset to
  // page 0. Our own "Load more" clicks set pageChangeRef to skip the reset.
  const pageChangeRef = useRef(false);
  const handleLoadMore = () => {
    pageChangeRef.current = true;
    setPage((p) => p + 1);
  };
  const prevFetchingRef = useRef(isFetching);
  const needsReset = !prevFetchingRef.current && isFetching && offset > 0 && !pageChangeRef.current;
  prevFetchingRef.current = isFetching;
  useEffect(() => {
    if (needsReset) {
      dataRef.current = undefined;
      setPage(0);
      setAllRuns([]);
    }
    if (!isFetching) pageChangeRef.current = false;
  }, [needsReset, isFetching]);

  const total = data?.total ?? allRuns.length;
  const hasMore = allRuns.length < total;
  const isLoadingMore = isFetching && allRuns.length > 0;

  const retryMut = useMutation({
    mutationFn: (runId: string) => retryFailedAnalysisRun(runId),
    onSuccess: (_data, runId) => {
      dataRef.current = undefined;
      setPage(0);
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["analysisRun", runId] });
      onSelectRun(runId);
    },
  });

  const resumeMut = useMutation({
    mutationFn: (runId: string) => resumeAnalysisRun(runId, true),
    onSuccess: (_data, runId) => {
      dataRef.current = undefined;
      setPage(0);
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["analysisRun", runId] });
      onSelectRun(runId);
    },
  });

  if (isLoading && allRuns.length === 0) return <LoadingBlock text="Loading run history..." />;
  if (isError && allRuns.length === 0) {
    const apiErr = error instanceof ApiError ? error : undefined;
    return (
      <div className="card">
        <h3>Run History</h3>
        <ErrorBlock
          title="Failed to load run history"
          message={apiErr?.detail ?? error?.message ?? "Unable to fetch run history."}
          status={apiErr?.status}
          onRetry={() => refetch()}
        />
      </div>
    );
  }
  if (allRuns.length === 0 && !isFetching) {
    return (
      <EmptyState
        title="No runs yet"
        description="Select an analysis mode above and click Run v2 Analysis to create your first run."
      />
    );
  }

  return (
    <div className="card" style={{ fontSize: "0.85rem" }}>
      <h3>Run History ({allRuns.length}/{total})</h3>
      <div style={{ maxHeight: 400, overflowY: "auto" }}>
        {allRuns.map((r) => (
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
        {isLoadingMore && <LoadingBlock text="Loading more..." />}
      </div>
      {hasMore && (
        <div style={{ marginTop: "0.5rem", textAlign: "center" }}>
          <button
            onClick={handleLoadMore}
            disabled={isFetching}
            style={{ fontSize: "0.78rem" }}
          >
            Load more ({total - allRuns.length} remaining)
          </button>
        </div>
      )}
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

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(); }}
      aria-label={`Run ${run.id.slice(0, 8)}: ${run.mode} ${run.status}`}
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
          <StatusBadge label={run.status} tone={statusTone(run.status)} />
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
            style={{ fontSize: "0.72rem", padding: "0.15em 0.5em" }}
            aria-label="Retry failed extractions for this run">
            {retrying ? "Retrying..." : "Retry Failed"}
          </button>
        )}
        {canRetry && (
          <button onClick={(e) => { e.stopPropagation(); onResume(); }} disabled={resuming}
            style={{ fontSize: "0.72rem", padding: "0.15em 0.5em" }}
            aria-label="Resume this run">
            {resuming ? "Resuming..." : "Resume"}
          </button>
        )}
      </div>
    </div>
  );
}
