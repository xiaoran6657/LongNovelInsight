import { apiRequest } from "./client";
import type {
  SearchRequest,
  SearchResponse,
  LocatorResponse,
} from "./types";

export function searchChunks(
  topicId: string,
  body: SearchRequest
): Promise<SearchResponse> {
  return apiRequest<SearchResponse>(`/api/topics/${topicId}/search`, {
    method: "POST",
    json: body,
  });
}

export function getChunkLocator(
  topicId: string,
  chunkId: string
): Promise<LocatorResponse> {
  return apiRequest<LocatorResponse>(
    `/api/topics/${topicId}/chunks/${chunkId}/locator`
  );
}
