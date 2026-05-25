import { apiRequest } from "./client";
import type { AnalysisOutput, Job, JobItem } from "./types";

interface OutputListResponse {
  outputs: AnalysisOutput[];
  count: number;
}

interface RunAnalysisResponse {
  outputs: AnalysisOutput[];
  count: number;
}

interface JobListResponse {
  jobs: Job[];
}

interface JobDetailResponse {
  job: Job;
}

interface AnalysisStatusResponse {
  topic_id: string;
  has_jobs: boolean;
  latest_job: Job | null;
  analysis_types_completed: string[];
}

export function listAnalysisOutputs(
  topicId: string,
  outputType?: string
): Promise<OutputListResponse> {
  const qs = outputType
    ? `?output_type=${encodeURIComponent(outputType)}`
    : "";
  return apiRequest<OutputListResponse>(
    `/api/topics/${topicId}/analysis/outputs${qs}`
  );
}

export function deleteAnalysisOutputs(
  topicId: string
): Promise<{ deleted: boolean; count: number }> {
  return apiRequest<{ deleted: boolean; count: number }>(
    `/api/topics/${topicId}/analysis/outputs`,
    { method: "DELETE" }
  );
}

export function runAnalysis(
  topicId: string,
  limitChunks: number = 5
): Promise<RunAnalysisResponse> {
  return apiRequest<RunAnalysisResponse>(
    `/api/topics/${topicId}/analysis/run?limit_chunks=${limitChunks}`,
    { method: "POST" }
  );
}

export function getAnalysisStatus(
  topicId: string
): Promise<AnalysisStatusResponse> {
  return apiRequest<AnalysisStatusResponse>(
    `/api/topics/${topicId}/analysis/status`
  );
}

export function listAnalysisJobs(topicId: string): Promise<JobListResponse> {
  return apiRequest<JobListResponse>(`/api/topics/${topicId}/analysis/jobs`);
}

export function getJobDetail(jobId: string): Promise<JobDetailResponse> {
  return apiRequest<JobDetailResponse>(`/api/analysis/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<JobDetailResponse> {
  return apiRequest<JobDetailResponse>(`/api/analysis/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function runAnalysisAsync(
  topicId: string,
  limitChunks: number = 5
): Promise<{ job: Job; items: JobItem[] }> {
  return apiRequest<{ job: Job; items: JobItem[] }>(
    `/api/topics/${topicId}/analysis/run-async?limit_chunks=${limitChunks}`,
    { method: "POST" }
  );
}

export function runSingleAnalysis(
  topicId: string,
  outputType: string,
  limitChunks: number = 5,
  deepen: boolean = false
): Promise<{ output: AnalysisOutput }> {
  const params = new URLSearchParams();
  params.set("limit_chunks", String(limitChunks));
  if (deepen) params.set("deepen", "true");
  return apiRequest<{ output: AnalysisOutput }>(
    `/api/topics/${topicId}/analysis/run/${outputType}?${params.toString()}`,
    { method: "POST" }
  );
}

// ── v0.2 Analysis Run API ──

import type {
  AnalysisRunCreateRequest,
  AnalysisRunListResponse,
  AnalysisRunDetail,
  CreateAnalysisRunResponse,
  RunRetryResponse,
  RunResumeResponse,
  RunCancelResponse,
  AnalysisStatusV2Response,
} from "./types";

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
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return apiRequest<AnalysisRunListResponse>(
    `/api/topics/${topicId}/analysis/runs${query ? `?${query}` : ""}`,
  );
}

export function getAnalysisRun(
  runId: string
): Promise<AnalysisRunDetail> {
  return apiRequest<AnalysisRunDetail>(`/api/analysis/runs/${runId}`);
}

export function cancelAnalysisRun(
  runId: string
): Promise<RunCancelResponse> {
  return apiRequest<RunCancelResponse>(
    `/api/analysis/runs/${runId}/cancel`,
    { method: "POST" }
  );
}

export function retryFailedAnalysisRun(
  runId: string
): Promise<RunRetryResponse> {
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

export function getAnalysisStatusV2(
  topicId: string
): Promise<AnalysisStatusV2Response> {
  return apiRequest<AnalysisStatusV2Response>(
    `/api/topics/${topicId}/analysis/status`
  );
}

export function runAnalysisV2(
  topicId: string,
  limitChunks: number = 5
): Promise<CreateAnalysisRunResponse> {
  return apiRequest<CreateAnalysisRunResponse>(
    `/api/topics/${topicId}/analysis/run?pipeline=v2&limit_chunks=${limitChunks}`,
    { method: "POST" }
  );
}
