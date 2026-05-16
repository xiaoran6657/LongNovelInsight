import { apiRequest } from "./client";
import type {
  Topic,
  TopicCreate,
  TopicProviderConfigData,
  EffectiveProviderConfig,
  AnalysisRecommendation,
} from "./types";

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

// Topic Provider Config

export function getTopicProviderConfig(
  topicId: string
): Promise<{ config: TopicProviderConfigData | null }> {
  return apiRequest<{ config: TopicProviderConfigData | null }>(
    `/api/topics/${topicId}/provider-config`
  );
}

export function updateTopicProviderConfig(
  topicId: string,
  data: Partial<TopicProviderConfigData>
): Promise<TopicProviderConfigData> {
  return apiRequest<TopicProviderConfigData>(
    `/api/topics/${topicId}/provider-config`,
    { method: "PUT", json: data }
  );
}

export function getEffectiveConfig(
  topicId: string
): Promise<EffectiveProviderConfig> {
  return apiRequest<EffectiveProviderConfig>(
    `/api/topics/${topicId}/provider-config/effective`
  );
}

export function getAnalysisRecommendation(
  topicId: string
): Promise<AnalysisRecommendation> {
  return apiRequest<AnalysisRecommendation>(
    `/api/topics/${topicId}/analysis/recommendation`
  );
}

export function applyRecommendation(
  topicId: string
): Promise<{ config: TopicProviderConfigData; recommendation: AnalysisRecommendation }> {
  return apiRequest<{ config: TopicProviderConfigData; recommendation: AnalysisRecommendation }>(
    `/api/topics/${topicId}/provider-config/apply-recommendation`,
    { method: "POST" }
  );
}
