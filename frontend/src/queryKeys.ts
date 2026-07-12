type QueryId = string | null | undefined;

export type ChunkListKeyOptions = {
  includeText?: boolean;
  limit?: number;
  offset?: number;
};

function id(value: QueryId): string | null {
  return value ?? null;
}

function chunkListOptions(options: ChunkListKeyOptions = {}) {
  return {
    includeText: options.includeText ?? false,
    limit: options.limit ?? null,
    offset: options.offset ?? null,
  } as const;
}

export const queryKeys = {
  topics: {
    all: ["topics"] as const,
    detail: (topicId: QueryId) => ["topic", id(topicId)] as const,
  },
  providers: {
    all: ["providers"] as const,
    presets: ["provider-presets"] as const,
  },
  topicConfig: {
    effective: (topicId: QueryId) =>
      ["effective-config", id(topicId)] as const,
    stored: (topicId: QueryId) => ["provider-config", id(topicId)] as const,
  },
  documents: {
    current: (topicId: QueryId) => ["document", id(topicId)] as const,
  },
  chapters: {
    list: (topicId: QueryId) => ["chapters", id(topicId)] as const,
  },
  chunks: {
    all: (topicId: QueryId) => ["chunks", id(topicId)] as const,
    meta: (topicId: QueryId) => ["chunks-meta", id(topicId)] as const,
    list: (topicId: QueryId, options: ChunkListKeyOptions = {}) =>
      ["chunks", id(topicId), "list", chunkListOptions(options)] as const,
  },
  works: {
    list: (topicId: QueryId) => ["works", id(topicId)] as const,
  },
  chat: {
    sessions: (topicId: QueryId) => ["chatSessions", id(topicId)] as const,
    messages: (sessionId: QueryId) =>
      ["chatMessages", id(sessionId)] as const,
  },
} as const;