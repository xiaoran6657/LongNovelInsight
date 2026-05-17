import { useState, useRef, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  listChatSessions,
  listChatMessages,
  sendChatMessage,
  deleteChatSession,
} from "../api/chat";
import { getTopic } from "../api/topics";
import type { ChatSessionRead, ChatMessageRead } from "../api/types";

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function TopicChatPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const queryClient = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Topic info (for back link title)
  const topicQuery = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => getTopic(topicId!),
    enabled: !!topicId,
  });

  // Session list
  const sessionsQuery = useQuery({
    queryKey: ["chatSessions", topicId],
    queryFn: () => listChatSessions(topicId!),
    enabled: !!topicId,
  });

  // Active session
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Messages for active session
  const messagesQuery = useQuery({
    queryKey: ["chatMessages", activeSessionId],
    queryFn: () => listChatMessages(activeSessionId!),
    enabled: !!activeSessionId,
  });

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesQuery.data]);

  // New session
  const [newTitle, setNewTitle] = useState("");
  const newSessionMut = useMutation({
    mutationFn: (title: string) => createChatSession(topicId!, title),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["chatSessions", topicId] });
      setActiveSessionId(data.id);
      setNewTitle("");
    },
    onError: () => {},
  });

  // Delete session
  const deleteMut = useMutation({
    mutationFn: (sid: string) => deleteChatSession(sid),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["chatSessions", topicId] });
      if (activeSessionId === deletedId) setActiveSessionId(null);
    },
  });

  // Send message
  const [draft, setDraft] = useState("");
  const sendMut = useMutation({
    mutationFn: ({ sid, content }: { sid: string; content: string }) =>
      sendChatMessage(sid, content),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
      setDraft("");
    },
  });

  const sessions: ChatSessionRead[] = sessionsQuery.data?.sessions ?? [];

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        <Link
          to={`/topics/${topicId}`}
          style={{ fontSize: "0.85rem", color: "#666" }}
        >
          &larr; Topic
          {topicQuery.data && ` — ${topicQuery.data.name}`}
        </Link>
      </div>

      <div className="chat-layout">
        {/* ── Session sidebar ── */}
        <aside className="chat-sidebar">
          <h3 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>
            Chat Sessions
          </h3>

          {/* New session form */}
          <div style={{ display: "flex", gap: "0.25rem", marginBottom: "0.5rem" }}>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newTitle.trim()) {
                  newSessionMut.mutate(newTitle.trim());
                }
              }}
              placeholder="Session title..."
              disabled={newSessionMut.isPending}
              style={{ flex: 1, minWidth: 0, fontSize: "0.78rem", padding: "0.3rem 0.4rem" }}
            />
            <button
              onClick={() => newTitle.trim() && newSessionMut.mutate(newTitle.trim())}
              disabled={!newTitle.trim() || newSessionMut.isPending}
              style={{ fontSize: "0.78rem", whiteSpace: "nowrap" }}
            >
              {newSessionMut.isPending ? "..." : "New"}
            </button>
          </div>
          {newSessionMut.isError && (
            <p className="field-error">
              {(newSessionMut.error as Error)?.message || "Failed to create session"}
            </p>
          )}

          {/* Session list */}
          {sessionsQuery.isLoading ? (
            <p className="text-dim">Loading...</p>
          ) : sessionsQuery.isError ? (
            <p className="field-error">Failed to load sessions</p>
          ) : sessions.length === 0 ? (
            <p className="text-dim">No sessions yet. Create one.</p>
          ) : (
            <ul className="chat-session-list">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  onClick={() => setActiveSessionId(s.id)}
                  className={
                    s.id === activeSessionId
                      ? "chat-session-item chat-session-item--active"
                      : "chat-session-item"
                  }
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        fontSize: "0.82rem",
                        fontWeight: 600,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {s.title}
                    </p>
                    <p className="text-dim" style={{ fontSize: "0.68rem" }}>
                      {fmtTime(s.created_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm("Delete this session and all messages?")) {
                        deleteMut.mutate(s.id);
                      }
                    }}
                    disabled={deleteMut.isPending && deleteMut.variables === s.id}
                    className="btn-danger"
                    style={{ fontSize: "0.65rem", padding: "0.1rem 0.35rem" }}
                  >
                    Del
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* ── Messages panel ── */}
        <section className="chat-messages-panel">
          {!activeSessionId ? (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1rem" }}>
              <p className="text-dim">Select or create a chat session to begin.</p>
            </div>
          ) : (
            <>
              {/* Messages */}
              <div className="chat-messages">
                {messagesQuery.isLoading ? (
                  <p className="text-dim">Loading messages...</p>
                ) : messagesQuery.isError ? (
                  <p className="field-error">Failed to load messages</p>
                ) : (
                  <>
                    {(messagesQuery.data?.messages ?? []).length === 0 && (
                      <p className="text-dim" style={{ textAlign: "center", padding: "2rem" }}>
                        No messages yet. Ask a question about the novel.
                      </p>
                    )}
                    {(messagesQuery.data?.messages ?? []).map((msg: ChatMessageRead) => (
                      <ChatBubble key={msg.id} message={msg} />
                    ))}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Input box */}
              <div className="chat-input-area">
                <div style={{ display: "flex", gap: "0.35rem" }}>
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        const trimmed = draft.trim();
                        if (trimmed && !sendMut.isPending) {
                          sendMut.mutate({ sid: activeSessionId, content: trimmed });
                        }
                      }
                    }}
                    placeholder={
                      sendMut.isPending
                        ? "Waiting for response..."
                        : "Ask a question about the novel... (Enter to send, Shift+Enter for newline)"
                    }
                    disabled={sendMut.isPending}
                    rows={2}
                    style={{ flex: 1, resize: "none", fontSize: "0.85rem" }}
                  />
                  <button
                    onClick={() => {
                      const trimmed = draft.trim();
                      if (trimmed && !sendMut.isPending) {
                        sendMut.mutate({ sid: activeSessionId, content: trimmed });
                      }
                    }}
                    disabled={!draft.trim() || sendMut.isPending}
                    style={{ alignSelf: "flex-end", whiteSpace: "nowrap" }}
                  >
                    {sendMut.isPending ? "..." : "Send"}
                  </button>
                </div>
                {sendMut.isError && (
                  <p className="field-error" style={{ marginTop: "0.25rem" }}>
                    {(sendMut.error as Error)?.message || "Failed to send message"}
                  </p>
                )}
                <p style={{ fontSize: "0.65rem", color: "#999", marginTop: "0.2rem" }}>
                  Responses use the LLM provider configured for this Topic. Each question
                  may consume API credits.
                </p>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

/* ── Chat bubble ── */

function ChatBubble({ message }: { message: ChatMessageRead }) {
  const isUser = message.role === "user";
  let evidence: unknown = null;
  let uncertainty: string | null = null;

  if (!isUser) {
    try {
      evidence = message.evidence_json
        ? JSON.parse(message.evidence_json)
        : null;
    } catch {
      evidence = message.evidence_json;
    }
    uncertainty = message.uncertainty;
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: "0.6rem",
      }}
    >
      <div
        style={{
          maxWidth: "82%",
          padding: "0.5rem 0.7rem",
          borderRadius: 8,
          background: isUser ? "#e3f2fd" : "#f5f5f5",
          border: isUser ? "1px solid #bbdefb" : "1px solid #e0e0e0",
          fontSize: "0.85rem",
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {/* Role label */}
        <div
          style={{
            fontSize: "0.65rem",
            fontWeight: 700,
            color: isUser ? "#1565c0" : "#555",
            marginBottom: "0.15rem",
          }}
        >
          {isUser ? "You" : "Assistant"}
        </div>

        {/* Content */}
        <div>{message.content}</div>

        {/* Evidence */}
        {!isUser && Array.isArray(evidence) && (evidence as unknown[]).length > 0 && (
          <div
            style={{
              marginTop: "0.5rem",
              borderTop: "1px solid #ddd",
              paddingTop: "0.35rem",
              fontSize: "0.75rem",
              color: "#555",
            }}
          >
            <p style={{ fontWeight: 600, marginBottom: "0.2rem" }}>
              Evidence ({String((evidence as unknown[]).length)})
            </p>
            <ul style={{ paddingLeft: "1.2rem", margin: 0 }}>
              {(evidence as unknown[]).map((eq, i) => (
                <li key={i} style={{ marginBottom: "0.15rem" }}>
                  {typeof eq === "string" ? eq : JSON.stringify(eq)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Uncertainty */}
        {!isUser && uncertainty && (
          <div
            style={{
              marginTop: "0.5rem",
              borderTop: "1px solid #fcd34d",
              paddingTop: "0.35rem",
              fontSize: "0.73rem",
              color: "#92400e",
              fontStyle: "italic",
            }}
          >
            Uncertainty: {uncertainty}
          </div>
        )}

        {/* Evidence empty state */}
        {!isUser &&
          (!evidence ||
            (Array.isArray(evidence) && (evidence as unknown[]).length === 0)) && (
            <div
              style={{
                marginTop: "0.35rem",
                fontSize: "0.7rem",
                color: "#999",
              }}
            >
              No evidence cited
            </div>
          )}

        {/* Timestamp */}
        <div
          className="text-dim"
          style={{ fontSize: "0.63rem", marginTop: "0.25rem" }}
        >
          {fmtTime(message.created_at)}
        </div>
      </div>
    </div>
  );
}
