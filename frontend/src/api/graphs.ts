import { apiRequest } from "./client";
import type { CharacterGraphResponse } from "./types";

export function getCharacterGraph(
  topicId: string,
  params: {
    work_id?: string;
    min_confidence?: number;
    min_weight?: number;
    relation_type?: string;
    limit_nodes?: number;
    include_evidence?: boolean;
  } = {}
): Promise<CharacterGraphResponse> {
  const sp = new URLSearchParams();
  if (params.work_id) sp.set("work_id", params.work_id);
  if (params.min_confidence != null) sp.set("min_confidence", String(params.min_confidence));
  if (params.min_weight != null) sp.set("min_weight", String(params.min_weight));
  if (params.relation_type) sp.set("relation_type", params.relation_type);
  if (params.limit_nodes != null) sp.set("limit_nodes", String(params.limit_nodes));
  if (params.include_evidence) sp.set("include_evidence", "true");
  return apiRequest<CharacterGraphResponse>(
    `/api/topics/${topicId}/graphs/characters?${sp}`
  );
}

export function buildGraph(
  topicId: string
): Promise<CharacterGraphResponse> {
  return apiRequest<CharacterGraphResponse>(
    `/api/topics/${topicId}/graphs/build`,
    { method: "POST" }
  );
}
