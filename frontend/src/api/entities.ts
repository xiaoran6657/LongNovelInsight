import { apiRequest } from "./client";
import type {
  EntityEvidenceResponse,
  SimilarScenesResponse,
} from "./types";

export function getEntityEvidence(
  topicId: string,
  entityId: string,
  limit?: number
): Promise<EntityEvidenceResponse> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set("limit", String(limit));
  const qs = params.toString();
  return apiRequest<EntityEvidenceResponse>(
    `/api/topics/${topicId}/entities/${encodeURIComponent(entityId)}/evidence${qs ? `?${qs}` : ""}`
  );
}

export function getSimilarScenes(
  topicId: string,
  params: {
    chunk_id?: string;
    query?: string;
    limit?: number;
  }
): Promise<SimilarScenesResponse> {
  const q = new URLSearchParams();
  if (params.chunk_id) q.set("chunk_id", params.chunk_id);
  if (params.query) q.set("query", params.query);
  if (params.limit !== undefined) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiRequest<SimilarScenesResponse>(
    `/api/topics/${topicId}/similar-scenes${qs ? `?${qs}` : ""}`
  );
}
