import { apiRequest } from "./client";
import type { RetrieveRequest, RetrieveResponse } from "./types";

export function retrieveTopic(
  topicId: string,
  body: RetrieveRequest
): Promise<RetrieveResponse> {
  return apiRequest<RetrieveResponse>(
    `/api/topics/${topicId}/retrieve`,
    {
      method: "POST",
      json: body,
    }
  );
}
