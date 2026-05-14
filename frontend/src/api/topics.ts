import { apiRequest } from "./client";
import type { Topic, TopicCreate } from "./types";

interface TopicListResponse {
  topics: Topic[];
}

export function listTopics(): Promise<TopicListResponse> {
  return apiRequest<TopicListResponse>("/api/topics");
}

export function getTopic(id: string): Promise<Topic> {
  return apiRequest<Topic>(`/api/topics/${id}`);
}

export function createTopic(data: TopicCreate): Promise<Topic> {
  return apiRequest<Topic>("/api/topics", {
    method: "POST",
    json: data,
  });
}

export function bindProvider(
  topicId: string,
  providerId: string
): Promise<Topic> {
  return apiRequest<Topic>(`/api/topics/${topicId}/provider`, {
    method: "PUT",
    json: { provider_id: providerId },
  });
}

export function deleteTopic(id: string): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/topics/${id}`, {
    method: "DELETE",
  });
}
