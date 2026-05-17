import { useState, useRef, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  listChatSessions,
  listChatMessages,
  sendChatMessage,
  deleteChatMessage,
  deleteChatSession,
} from "../api/chat";
import { getTopic } from "../api/topics";
import type { ChatSessionRead, ChatMessageRead } from "../api/types";

function fmtTime(iso: string): string {
  try {
    // Backend stores UTC; if the ISO string lacks a timezone marker, append Z
    const normalized = /[+\-Zz]\d*$/.test(iso.trimEnd()) ? iso : iso + "Z";
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return iso;
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
  const optimisticIdRef = useRef(0);
  const sendMut = useMutation({
    mutationFn: ({ sid, content }: { sid: string; content: string }) =>
      sendChatMessage(sid, content),
    onMutate: async ({ content }) => {
      setDraft("");
      await queryClient.cancelQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
      const prev = queryClient.getQueryData<{
        messages: ChatMessageRead[];
        total: number;
      }>(["chatMessages", activeSessionId]);
      const opt: ChatMessageRead = {
        id: `optimistic-${++optimisticIdRef.current}`,
        session_id: activeSessionId!,
        role: "user",
        content,
        evidence_json: null,
        uncertainty: null,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData(["chatMessages", activeSessionId], {
        messages: [...(prev?.messages ?? []), opt],
        total: (prev?.total ?? 0) + 1,
      });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(
          ["chatMessages", activeSessionId],
          ctx.prev
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
    },
  });

  // Delete message (with confirmation handled in ChatBubble)
  const deleteMsgMut = useMutation({
    mutationFn: (msgId: string) => deleteChatMessage(msgId),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
    },
  });

  // Edit & resend: delete old pair, then send new content
  const editResendMut = useMutation({
    mutationFn: async ({
      oldMsgId,
      content,
    }: {
      oldMsgId: string;
      content: string;
    }) => {
      await deleteChatMessage(oldMsgId);
      await new Promise((r) => setTimeout(r, 100)); // let backend commit
      return sendChatMessage(activeSessionId!, content);
    },
    onMutate: async ({ content }) => {
      setDraft("");
      await queryClient.cancelQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
      const prev = queryClient.getQueryData<{
        messages: ChatMessageRead[];
        total: number;
      }>(["chatMessages", activeSessionId]);
      const opt: ChatMessageRead = {
        id: `optimistic-${++optimisticIdRef.current}`,
        session_id: activeSessionId!,
        role: "user",
        content,
        evidence_json: null,
        uncertainty: null,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData(["chatMessages", activeSessionId], {
        messages: [...(prev?.messages ?? []), opt],
        total: (prev?.total ?? 0) + 1,
      });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(
          ["chatMessages", activeSessionId],
          ctx.prev
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["chatMessages", activeSessionId],
      });
    },
  });

  const [sidebarOpen, setSidebarOpen] = useState(true);

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
        <aside
          className="chat-sidebar"
          style={{
            width: sidebarOpen ? "14rem" : "2.2rem",
            paddingRight: sidebarOpen ? "0.75rem" : "0.3rem",
            overflow: sidebarOpen ? "auto" : "visible",
            transition: "width 0.2s, padding-right 0.2s",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "0.5rem",
            }}
          >
            {sidebarOpen && (
              <h3 style={{ fontSize: "0.9rem", margin: 0 }}>Chat Sessions</h3>
            )}
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              style={{
                fontSize: "0.8rem",
                padding: "0.15rem 0.35rem",
                lineHeight: 1,
                flexShrink: 0,
                marginLeft: sidebarOpen ? "0.25rem" : 0,
              }}
            >
              {sidebarOpen ? "◀" : "▶"}
            </button>
          </div>

          {sidebarOpen && (
            <>
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
            </>
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
                      <ChatBubble
                        key={msg.id}
                        message={msg}
                        onDelete={(id) => deleteMsgMut.mutate(id)}
                        onEditResend={(id, content) =>
                          editResendMut.mutate({ oldMsgId: id, content })
                        }
                        isResending={editResendMut.isPending}
                      />
                    ))}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Input box */}
              <div className="chat-input-area">
                <div style={{ display: "flex", gap: "0.35rem", alignItems: "flex-end" }}>
                  <textarea
                    ref={(el) => {
                      if (el) {
                        el.style.height = "auto";
                        el.style.height = el.scrollHeight + "px";
                      }
                    }}
                    value={draft}
                    onChange={(e) => {
                      setDraft(e.target.value);
                      requestAnimationFrame(() => {
                        const t = e.target;
                        t.style.height = "auto";
                        t.style.height = t.scrollHeight + "px";
                      });
                    }}
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
                    rows={1}
                    style={{
                      flex: 1,
                      fontSize: "0.85rem",
                      fontFamily: "inherit",
                      padding: "0.5rem 0.6rem",
                      border: "1px solid #bdbdbd",
                      borderRadius: 6,
                      background: "#fafafa",
                      outline: "none",
                      resize: "none",
                      overflow: "hidden",
                      transition: "border-color 0.15s",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#4fc3f7";
                      e.target.style.boxShadow =
                        "0 0 0 2px rgba(79,195,247,0.2)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "#bdbdbd";
                      e.target.style.boxShadow = "none";
                    }}
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

const ACTION_BTN_STYLE: React.CSSProperties = {
  background: "transparent",
  border: "1px solid transparent",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: "0.9rem",
  padding: "0.1rem 0.3rem",
  lineHeight: 1,
  position: "relative",
};

function ActionBtn({
  icon,
  label,
  onClick,
}: {
  icon: string;
  label: string;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        style={{
          ...ACTION_BTN_STYLE,
          background: hover ? "#eee" : "transparent",
        }}
      >
        {icon}
      </button>
      {hover && (
        <span
          style={{
            position: "absolute",
            top: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: "0.6rem",
            color: "#555",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            marginTop: 2,
          }}
        >
          {label}
        </span>
      )}
    </span>
  );
}

function ChatBubble({
  message,
  onDelete,
  onEditResend,
  isResending,
}: {
  message: ChatMessageRead;
  onDelete: (id: string) => void;
  onEditResend: (id: string, content: string) => void;
  isResending: boolean;
}) {
  const isUser = message.role === "user";
  const isOptimistic = message.id.startsWith("optimistic-");
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(message.content);
  const [hover, setHover] = useState(false);
  const [copied, setCopied] = useState(false);

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

  function handleCopy() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function handleEditSend() {
    const trimmed = editText.trim();
    if (!trimmed || isResending) return;
    onEditResend(message.id, trimmed);
    setEditing(false);
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: "0.6rem",
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div
        style={{
          maxWidth: "82%",
          padding: "0.5rem 0.7rem",
          borderRadius: 8,
          background: isUser ? "#e3f2fd" : "#fff8e1",
          border: isUser ? "1px solid #bbdefb" : "1px solid #ffe0b2",
          fontSize: "0.85rem",
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          position: "relative",
          opacity: isOptimistic ? 0.7 : 1,
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
          {isOptimistic && " (sending...)"}
        </div>

        {/* Content or edit mode */}
        {editing ? (
          <div style={{ minWidth: "28rem", maxWidth: "100%" }}>
            <textarea
              ref={(el) => {
                if (el) {
                  el.style.height = "auto";
                  el.style.height = el.scrollHeight + "px";
                }
              }}
              value={editText}
              onChange={(e) => {
                setEditText(e.target.value);
                // Auto-resize on next tick after React re-render
                requestAnimationFrame(() => {
                  const t = e.target;
                  t.style.height = "auto";
                  t.style.height = t.scrollHeight + "px";
                });
              }}
              rows={1}
              disabled={isResending}
              style={{
                width: "100%",
                minWidth: "28rem",
                fontSize: "0.85rem",
                fontFamily: "inherit",
                padding: "0.35rem",
                overflow: "hidden",
              }}
            />
            <div
              style={{
                display: "flex",
                gap: "0.35rem",
                marginTop: "0.35rem",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => {
                  setEditing(false);
                  setEditText(message.content);
                }}
                disabled={isResending}
                style={{ fontSize: "0.72rem" }}
              >
                Cancel
              </button>
              <button
                onClick={handleEditSend}
                disabled={!editText.trim() || isResending}
                style={{ fontSize: "0.72rem" }}
              >
                {isResending ? "..." : "Resend"}
              </button>
            </div>
          </div>
        ) : (
          <div>{message.content}</div>
        )}

        {/* Evidence — assistant only */}
        {!isUser && !editing && (
          <>
            {Array.isArray(evidence) &&
            (evidence as unknown[]).length > 0 ? (
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
            ) : (
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
            {uncertainty && (
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
          </>
        )}

        {/* Timestamp */}
        <div
          className="text-dim"
          style={{ fontSize: "0.63rem", marginTop: "0.25rem" }}
        >
          {fmtTime(message.created_at)}
        </div>

        {/* Action buttons — shown on hover */}
        {hover && !editing && (
          <div
            style={{
              position: "absolute",
              bottom: "0.25rem",
              right: "0.3rem",
              display: "flex",
              gap: "0.15rem",
              background: "rgba(255,255,255,0.85)",
              borderRadius: 6,
              padding: "0.1rem 0.2rem",
            }}
          >
            <ActionBtn
              icon={copied ? "✓" : "⎘"}
              label={copied ? "Copied" : "Copy"}
              onClick={handleCopy}
            />
            {isUser && !isOptimistic && (
              <>
                <ActionBtn
                  icon={"✎"}
                  label="Edit"
                  onClick={() => {
                    setEditText(message.content);
                    setEditing(true);
                  }}
                />
                <ActionBtn
                  icon={"✗"}
                  label="Delete"
                  onClick={() => {
                    if (
                      window.confirm(
                        "Delete this message and the LLM response below it?\n\nThis cannot be undone."
                      )
                    ) {
                      onDelete(message.id);
                    }
                  }}
                />
              </>
            )}
            {!isUser && !isOptimistic && (
              <ActionBtn
                icon={"✗"}
                label="Delete"
                onClick={() => {
                  if (
                    window.confirm(
                      "Delete this LLM response? The question will remain."
                    )
                  ) {
                    onDelete(message.id);
                  }
                }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
