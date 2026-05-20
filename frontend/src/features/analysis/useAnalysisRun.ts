import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createAnalysisRun, getAnalysisRun, cancelAnalysisRun } from "../../api/analysis";
import type { AnalysisRunCreateRequest, AnalysisRunDetail } from "../../api/types";

export function useAnalysisRun(runId: string | null, topicId: string) {
  const qc = useQueryClient();

  const runQuery = useQuery({
    queryKey: ["analysisRun", runId],
    queryFn: () => getAnalysisRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.run.status;
      if (status === "succeeded" || status === "partial_success" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 2500;
    },
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelAnalysisRun(runId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysisRun", runId] });
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
    },
  });

  return { runQuery, cancelMut };
}

export function useCreateAnalysisRun(topicId: string) {
  const qc = useQueryClient();

  const createMut = useMutation({
    mutationFn: (body: AnalysisRunCreateRequest) => createAnalysisRun(topicId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
    },
  });

  return createMut;
}

export function isRunActive(status: string | undefined): boolean {
  return status === "pending" || status === "running";
}

export function isRunTerminal(status: string | undefined): boolean {
  return status === "succeeded" || status === "partial_success" || status === "failed" || status === "cancelled";
}

export function runProgressPercent(run: AnalysisRunDetail["run"] | undefined): number {
  if (!run || run.progress_total === 0) return 0;
  return Math.round((run.progress_current / run.progress_total) * 100);
}
