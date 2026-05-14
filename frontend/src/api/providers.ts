import { apiRequest } from "./client";
import type {
  ModelProvider,
  ModelProviderCreate,
  ModelProviderUpdate,
  ProviderTestResult,
} from "./types";

interface ProviderListResponse {
  providers: ModelProvider[];
}

export function listProviders(): Promise<ProviderListResponse> {
  return apiRequest<ProviderListResponse>("/api/providers");
}

export function getProvider(id: string): Promise<ModelProvider> {
  return apiRequest<ModelProvider>(`/api/providers/${id}`);
}

export function createProvider(
  data: ModelProviderCreate
): Promise<ModelProvider> {
  return apiRequest<ModelProvider>("/api/providers", {
    method: "POST",
    json: data,
  });
}

export function updateProvider(
  id: string,
  data: ModelProviderUpdate
): Promise<ModelProvider> {
  return apiRequest<ModelProvider>(`/api/providers/${id}`, {
    method: "PATCH",
    json: data,
  });
}

export function deleteProvider(id: string): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/providers/${id}`, {
    method: "DELETE",
  });
}

export function testProvider(id: string): Promise<ProviderTestResult> {
  return apiRequest<ProviderTestResult>(`/api/providers/${id}/test`, {
    method: "POST",
  });
}
