import { apiRequest } from "./client";
import type {
  CrossWorkRun,
  CrossWorkRunCreateRequest,
  CrossWorkRunCreateResponse,
  CrossWorkRunListResponse,
  EntityListResponse,
  GlobalEntity,
  EntityMentionListResponse,
} from "./types";

// ── Cross-work runs ──

export function createCrossWorkRun(
  topicId: string,
  body: CrossWorkRunCreateRequest
): Promise<CrossWorkRunCreateResponse> {
  return apiRequest<CrossWorkRunCreateResponse>(`/api/topics/${topicId}/cross-work/runs`, {
    method: "POST",
    json: body,
  });
}

export function listCrossWorkRuns(
  topicId: string,
  limit = 20,
  offset = 0
): Promise<CrossWorkRunListResponse> {
  return apiRequest<CrossWorkRunListResponse>(
    `/api/topics/${topicId}/cross-work/runs?limit=${limit}&offset=${offset}`
  );
}

export function getCrossWorkRun(topicId: string, runId: string): Promise<CrossWorkRun> {
  return apiRequest<CrossWorkRun>(`/api/topics/${topicId}/cross-work/runs/${runId}`);
}

// ── Entity registry ──

export function listEntities(
  topicId: string,
  params: {
    entity_type?: string;
    work_id?: string;
    q?: string;
    min_confidence?: number;
    limit?: number;
    offset?: number;
    sort?: string;
  } = {}
): Promise<EntityListResponse> {
  const sp = new URLSearchParams();
  if (params.entity_type) sp.set("entity_type", params.entity_type);
  if (params.work_id) sp.set("work_id", params.work_id);
  if (params.q) sp.set("q", params.q);
  if (params.min_confidence != null) sp.set("min_confidence", String(params.min_confidence));
  sp.set("limit", String(params.limit ?? 50));
  sp.set("offset", String(params.offset ?? 0));
  if (params.sort) sp.set("sort", params.sort);
  return apiRequest<EntityListResponse>(`/api/topics/${topicId}/entities?${sp}`);
}

export function getEntity(topicId: string, entityId: string): Promise<GlobalEntity> {
  return apiRequest<GlobalEntity>(`/api/topics/${topicId}/entities/${entityId}`);
}

export function listEntityMentions(
  topicId: string,
  entityId: string,
  limit = 50,
  offset = 0
): Promise<EntityMentionListResponse> {
  return apiRequest<EntityMentionListResponse>(
    `/api/topics/${topicId}/entities/${entityId}/mentions?limit=${limit}&offset=${offset}`
  );
}

export function buildEntityRegistry(
  topicId: string
): Promise<{ entity_count: number; mention_count: number; warnings: string[] }> {
  return apiRequest<{ entity_count: number; mention_count: number; warnings: string[] }>(
    `/api/topics/${topicId}/cross-work/build`,
    { method: "POST" }
  );
}
