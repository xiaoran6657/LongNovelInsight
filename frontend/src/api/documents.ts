import { apiRequest } from "./client";
import type { Document, DocumentMetadata } from "./types";

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

export function getDocumentMetadata(
  topicId: string
): Promise<DocumentMetadata> {
  return apiRequest<DocumentMetadata>(
    `/api/topics/${topicId}/documents/current/metadata`
  );
}

export function deleteCurrentDocument(
  topicId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    `/api/topics/${topicId}/documents/current`,
    { method: "DELETE" }
  );
}
