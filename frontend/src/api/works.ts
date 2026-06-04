import { apiRequest } from "./client";
import type {
  WorkItem,
  WorkCreate,
  WorkUpdate,
  WorkListResponse,
  Document,
  ParseResult,
  Chapter,
  Chunk,
  AnalysisRunCreateSummary,
  AnalysisRunListResponse,
  AnalysisOutput,
} from "./types";

// ── CRUD ──

export function listWorks(topicId: string): Promise<WorkListResponse> {
  return apiRequest<WorkListResponse>(`/api/topics/${topicId}/works`);
}

export function createWork(topicId: string, body: WorkCreate): Promise<WorkItem> {
  return apiRequest<WorkItem>(`/api/topics/${topicId}/works`, {
    method: "POST",
    json: body,
  });
}

export function getWork(workId: string): Promise<WorkItem> {
  return apiRequest<WorkItem>(`/api/works/${workId}`);
}

export function updateWork(workId: string, body: WorkUpdate): Promise<WorkItem> {
  return apiRequest<WorkItem>(`/api/works/${workId}`, {
    method: "PATCH",
    json: body,
  });
}

export function deleteWork(workId: string): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/works/${workId}`, {
    method: "DELETE",
  });
}

// ── Document ──

export function uploadToWork(workId: string, file: File): Promise<Document> {
  const fd = new FormData();
  fd.append("file", file);
  return apiRequest<Document>(`/api/works/${workId}/documents/upload`, {
    method: "POST",
    formData: fd,
  });
}

export function getWorkDocument(workId: string): Promise<Document> {
  return apiRequest<Document>(`/api/works/${workId}/documents/current`);
}

export function getWorkMetadata(workId: string): Promise<Record<string, unknown>> {
  return apiRequest<Record<string, unknown>>(`/api/works/${workId}/metadata`);
}

// ── Parse ──

export function parseWork(workId: string, force = false): Promise<ParseResult> {
  const qs = force ? "?force=true" : "";
  return apiRequest<ParseResult>(`/api/works/${workId}/parse${qs}`, {
    method: "POST",
  });
}

export function listWorkChapters(workId: string): Promise<{ chapters: Chapter[] }> {
  return apiRequest<{ chapters: Chapter[] }>(`/api/works/${workId}/chapters`);
}

export function listWorkChunks(
  workId: string,
  includeText = false,
  limit = 100,
  offset = 0
): Promise<{ chunks: Chunk[] }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (includeText) params.set("include_text", "true");
  return apiRequest<{ chunks: Chunk[] }>(`/api/works/${workId}/chunks?${params}`);
}

// ── Analysis ──

export function createWorkAnalysisRun(
  workId: string,
  body: Record<string, unknown>
): Promise<{ run: AnalysisRunCreateSummary; status_url: string }> {
  return apiRequest<{ run: AnalysisRunCreateSummary; status_url: string }>(
    `/api/works/${workId}/analysis/runs`,
    { method: "POST", json: body }
  );
}

export function listWorkAnalysisRuns(
  workId: string,
  limit = 50,
  offset = 0
): Promise<AnalysisRunListResponse> {
  return apiRequest<AnalysisRunListResponse>(
    `/api/works/${workId}/analysis/runs?limit=${limit}&offset=${offset}`
  );
}

export function listWorkAnalysisOutputs(
  workId: string
): Promise<{ outputs: AnalysisOutput[]; total: number }> {
  return apiRequest<{ outputs: AnalysisOutput[]; total: number }>(
    `/api/works/${workId}/analysis/outputs`
  );
}
