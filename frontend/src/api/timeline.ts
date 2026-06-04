import { apiRequest } from "./client";
import type { TimelineResponse } from "./types";

export function getTimeline(
  topicId: string,
  params: {
    work_id?: string;
    participant_entity_id?: string;
    min_confidence?: number;
    limit?: number;
    offset?: number;
  } = {}
): Promise<TimelineResponse> {
  const sp = new URLSearchParams();
  if (params.work_id) sp.set("work_id", params.work_id);
  if (params.participant_entity_id) sp.set("participant_entity_id", params.participant_entity_id);
  if (params.min_confidence != null) sp.set("min_confidence", String(params.min_confidence));
  sp.set("limit", String(params.limit ?? 50));
  sp.set("offset", String(params.offset ?? 0));
  return apiRequest<TimelineResponse>(
    `/api/topics/${topicId}/timeline?${sp}`
  );
}

export function buildTimeline(
  topicId: string
): Promise<{ item_count: number; warnings: string[] }> {
  return apiRequest<{ item_count: number; warnings: string[] }>(
    `/api/topics/${topicId}/timeline/build`,
    { method: "POST" }
  );
}
