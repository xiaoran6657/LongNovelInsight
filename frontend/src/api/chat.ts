import { apiRequest } from "./client";
import type { ChatSessionRead, ChatMessageRead, ChatAnswerRead } from "./types";

interface SessionListResponse {
  sessions: ChatSessionRead[];
}

interface MessageListResponse {
  messages: ChatMessageRead[];
  total: number;
}

export function createChatSession(
  topicId: string,
  title: string
): Promise<ChatSessionRead> {
  return apiRequest<ChatSessionRead>(
    `/api/topics/${topicId}/chat/sessions`,
    { method: "POST", json: { title } }
  );
}

export function listChatSessions(
  topicId: string
): Promise<SessionListResponse> {
  return apiRequest<SessionListResponse>(
    `/api/topics/${topicId}/chat/sessions`
  );
}

export function listChatMessages(
  sessionId: string
): Promise<MessageListResponse> {
  return apiRequest<MessageListResponse>(
    `/api/chat/sessions/${sessionId}/messages`
  );
}

export function sendChatMessage(
  sessionId: string,
  content: string
): Promise<ChatAnswerRead> {
  return apiRequest<ChatAnswerRead>(
    `/api/chat/sessions/${sessionId}/messages`,
    { method: "POST", json: { content } }
  );
}

export function resendChatMessage(
  sessionId: string,
  messageId: string,
  content: string,
  expectedAssistantMessageId: string,
): Promise<ChatAnswerRead> {
  return apiRequest<ChatAnswerRead>(
    `/api/chat/sessions/${sessionId}/messages/${messageId}/resend`,
    {
      method: "POST",
      json: {
        content,
        expected_assistant_message_id: expectedAssistantMessageId,
      },
    },
  );
}

export function deleteChatMessage(
  messageId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    `/api/chat/sessions/messages/${messageId}`,
    { method: "DELETE" }
  );
}

export function deleteChatSession(
  sessionId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    `/api/chat/sessions/${sessionId}`,
    { method: "DELETE" }
  );
}
