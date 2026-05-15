import { apiRequest } from "./client";
import type { AnalysisOutput, Job } from "./types";

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
