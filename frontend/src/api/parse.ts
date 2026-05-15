import { apiRequest } from "./client";
import type { ParseResult, Chapter, Chunk, StorageInfo } from "./types";

interface ChapterListResponse {
  chapters: Chapter[];
}

interface ChunkListResponse {
  chunks: Chunk[];
}

interface ChunkListParams {
  include_text?: boolean;
  limit?: number;
  offset?: number;
}

export function parseTopic(topicId: string): Promise<ParseResult> {
  return apiRequest<ParseResult>(`/api/topics/${topicId}/parse`, {
    method: "POST",
  });
}

export function listChapters(topicId: string): Promise<ChapterListResponse> {
  return apiRequest<ChapterListResponse>(`/api/topics/${topicId}/chapters`);
}

export function listChunks(
  topicId: string,
  params: ChunkListParams = {}
): Promise<ChunkListResponse> {
  const query = new URLSearchParams();
  if (params.include_text !== undefined)
    query.set("include_text", String(params.include_text));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiRequest<ChunkListResponse>(
    `/api/topics/${topicId}/chunks${qs ? `?${qs}` : ""}`
  );
}

export interface ChunkMeta {
  count: number;
  total_chars: number;
  estimated_tokens: number;
}

export function getChunksMeta(topicId: string): Promise<ChunkMeta> {
  return apiRequest<ChunkMeta>(`/api/topics/${topicId}/chunks/meta`);
}

export function getStorage(topicId: string): Promise<StorageInfo> {
  return apiRequest<StorageInfo>(`/api/topics/${topicId}/storage`);
}
