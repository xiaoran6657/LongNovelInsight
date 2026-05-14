import { apiRequest } from "./client";
import type { Document } from "./types";

export function uploadDocument(
  topicId: string,
  file: File
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<Document>(`/api/topics/${topicId}/documents/upload`, {
    method: "POST",
    formData,
  });
}

export function getCurrentDocument(topicId: string): Promise<Document> {
  return apiRequest<Document>(`/api/topics/${topicId}/documents/current`);
}

export function deleteCurrentDocument(
  topicId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    `/api/topics/${topicId}/documents/current`,
    { method: "DELETE" }
  );
}
