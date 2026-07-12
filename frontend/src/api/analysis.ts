import { apiRequest } from "./client";
import type {
  AnalysisOutput,
  AnalysisRunCreateRequest,
  AnalysisRunDetail,
  AnalysisRunListResponse,
  CreateAnalysisRunResponse,
  RunCancelResponse,
  RunResumeResponse,
  RunRetryResponse,
} from "./types";

type OutputListResponse = {
  outputs: AnalysisOutput[];
  count: number;
};

export function deleteAnalysisOutputs(
  topicId: string
): Promise<{ deleted: boolean; count: number }> {
  return apiRequest<{ deleted: boolean; count: number }>(
    `/api/topics/${topicId}/analysis/outputs`,
    { method: "DELETE" }
  );
}

export function createAnalysisRun(
  topicId: string,
  body: AnalysisRunCreateRequest
): Promise<CreateAnalysisRunResponse> {
  return apiRequest<CreateAnalysisRunResponse>(
    `/api/topics/${topicId}/analysis/runs`,
    { method: "POST", json: body as unknown as Record<string, unknown> }
  );
}

export function listAnalysisRuns(
  topicId: string,
  params?: { limit?: number; offset?: number },
): Promise<AnalysisRunListResponse> {
  const query = new URLSearchParams();
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiRequest<AnalysisRunListResponse>(
    `/api/topics/${topicId}/analysis/runs${qs ? `?${qs}` : ""}`,
  );
}

export function getAnalysisRun(runId: string): Promise<AnalysisRunDetail> {
  return apiRequest<AnalysisRunDetail>(`/api/analysis/runs/${runId}`);
}

export function cancelAnalysisRun(runId: string): Promise<RunCancelResponse> {
  return apiRequest<RunCancelResponse>(
    `/api/analysis/runs/${runId}/cancel`,
    { method: "POST" }
  );
}

export function retryFailedAnalysisRun(runId: string): Promise<RunRetryResponse> {
  return apiRequest<RunRetryResponse>(
    `/api/analysis/runs/${runId}/retry-failed`,
    { method: "POST" }
  );
}

export function resumeAnalysisRun(
  runId: string,
  retryFailed: boolean = true
): Promise<RunResumeResponse> {
  const qs = retryFailed ? "?retry_failed=true" : "?retry_failed=false";
  return apiRequest<RunResumeResponse>(
    `/api/analysis/runs/${runId}/resume${qs}`,
    { method: "POST" }
  );
}

export function listAnalysisOutputsV2(
  topicId: string,
  params?: {
    outputType?: string;
    runId?: string;
    latestOnly?: boolean;
  }
): Promise<OutputListResponse> {
  const query = new URLSearchParams();
  if (params?.outputType) query.set("output_type", params.outputType);
  if (params?.runId) query.set("run_id", params.runId);
  if (params?.latestOnly) query.set("latest_only", "true");
  const qs = query.toString();
  return apiRequest<OutputListResponse>(
    `/api/topics/${topicId}/analysis/outputs${qs ? `?${qs}` : ""}`
  );
}
