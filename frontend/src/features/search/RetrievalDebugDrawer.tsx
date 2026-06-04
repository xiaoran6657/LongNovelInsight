import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { retrieveTopic } from "../../api/retrieve";
import type { RetrieveResponse, RetrieveMethod } from "../../api/types";
import RetrievalMethodBadge from "./RetrievalMethodBadge";

interface Props {
  topicId: string;
  query: string;
  workIds?: string[] | null;
  onClose: () => void;
}

const ALL_RETRIEVE_METHODS: {
  key: RetrieveMethod;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
}[] = [
  { key: "fts", label: "FTS" },
  { key: "keyword_fallback", label: "Keyword Fallback" },
  { key: "structured", label: "Structured" },
  { key: "analysis_output", label: "Analysis Output" },
  {
    key: "semantic_rerank",
    label: "Semantic Rerank",
    disabled: true,
    disabledReason: "Backend feature flag ENABLE_SEMANTIC_RERANK is off",
  },
];

function formatScore(score: number): string {
  return score.toFixed(3);
}

function sourceLocatorSummary(
  locator: Record<string, unknown> | null
): string | null {
  if (!locator) return null;
  const href = locator.href ?? locator.source_href;
  const parts: string[] = [];
  if (typeof href === "string") {
    const segments = href.split("/");
    parts.push(segments[segments.length - 1] || href);
  }
  if (typeof locator.chapter_index === "number") {
    parts.push(`Ch.${locator.chapter_index + 1}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export default function RetrievalDebugDrawer({
  topicId,
  query,
  workIds,
  onClose,
}: Props) {
  const [methods, setMethods] = useState<Set<RetrieveMethod>>(
    new Set(["fts", "keyword_fallback"])
  );

  const debugMut = useMutation({
    mutationFn: (q: string) =>
      retrieveTopic(topicId, {
        query: q,
        top_k: 20,
        persist_trace: true,
        methods: [...methods],
        work_ids: workIds ?? null,
      }),
  });

  function toggleMethod(m: RetrieveMethod) {
    setMethods((prev) => {
      const next = new Set(prev);
      if (next.has(m)) {
        if (next.size > 1) next.delete(m);
      } else {
        next.add(m);
      }
      return next;
    });
  }

  const runDebug = () => {
    if (debugMut.isPending) return;
    debugMut.mutate(query);
  };

  const response: RetrieveResponse | undefined = debugMut.data;

  return (
    <div
      style={{
        marginTop: "0.75rem",
        border: "1px solid #b0bec5",
        borderRadius: 4,
        background: "#fafbfc",
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.6rem 0.75rem",
          borderBottom: response ? "1px solid #e0e0e0" : "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <strong style={{ fontSize: "0.82rem" }}>Retrieval Debug</strong>
          {!response && !debugMut.isPending && !debugMut.isError && (
            <span className="text-dim" style={{ fontSize: "0.7rem" }}>
              Call POST /retrieve with the same query to inspect evidence
              sources.
            </span>
          )}
        </div>
        {/* ── Method checkboxes (idle state only) ── */}
        {!response && !debugMut.isPending && !debugMut.isError && (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.35rem" }}>
            {ALL_RETRIEVE_METHODS.map(({ key, label, disabled, disabledReason }) => (
              <label
                key={key}
                title={disabled ? disabledReason : undefined}
                style={{
                  fontSize: "0.73rem",
                  cursor: disabled ? "not-allowed" : "pointer",
                  opacity: disabled ? 0.55 : 1,
                }}
              >
                <input
                  type="checkbox"
                  checked={methods.has(key)}
                  onChange={() => toggleMethod(key)}
                  disabled={disabled}
                  style={{ marginRight: "0.2rem" }}
                />
                {label}
                {disabled && (
                  <span
                    style={{
                      fontSize: "0.6rem",
                      color: "#999",
                      marginLeft: "0.15rem",
                    }}
                  >
                    (off)
                  </span>
                )}
              </label>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: "0.4rem" }}>
          {!response && !debugMut.isPending && !debugMut.isError && (
            <button
              onClick={runDebug}
              style={{ fontSize: "0.72rem" }}
            >
              Run Retrieval
            </button>
          )}
          {debugMut.isPending && (
            <button disabled style={{ fontSize: "0.72rem" }}>
              Running...
            </button>
          )}
          <button onClick={onClose} className="btn-danger" style={{ fontSize: "0.72rem" }}>
            Close
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {debugMut.isError && (
        <div style={{ padding: "0.75rem" }}>
          <p className="field-error">
            {debugMut.error instanceof Error
              ? debugMut.error.message
              : "Retrieval failed"}
          </p>
        </div>
      )}

      {/* ── Results ── */}
      {response && (
        <div style={{ padding: "0.75rem" }}>
          {/* Query + trace */}
          <p style={{ fontSize: "0.78rem", marginBottom: "0.3rem" }}>
            <span className="text-dim">Query:</span> {response.query}
          </p>
          {response.trace_id && (
            <p style={{ fontSize: "0.72rem", marginBottom: "0.3rem" }}>
              <span className="text-dim">Trace ID:</span>{" "}
              <code style={{ fontSize: "0.7rem" }}>{response.trace_id}</code>
            </p>
          )}

          {/* Warning */}
          {response.warning && (
            <div
              style={{
                padding: "0.4rem 0.6rem",
                marginBottom: "0.5rem",
                background: "#fff8e1",
                border: "1px solid #ffcc02",
                borderRadius: 3,
                fontSize: "0.75rem",
                color: "#f57f17",
              }}
            >
              {response.warning}
            </div>
          )}

          {/* Empty */}
          {response.results.length === 0 && (
            <p className="text-dim" style={{ marginTop: "0.25rem" }}>
              No candidates returned.
            </p>
          )}

          {/* Candidate count */}
          {response.results.length > 0 && (
            <p
              className="text-dim"
              style={{
                fontSize: "0.75rem",
                marginBottom: "0.5rem",
                marginTop: "0.25rem",
              }}
            >
              {response.results.length} candidate
              {response.results.length !== 1 ? "s" : ""}
            </p>
          )}

          {/* Candidate list */}
          {response.results.map((c, i) => {
            const locSummary = sourceLocatorSummary(c.source_locator);
            return (
              <div
                key={`${c.chunk_id ?? c.source_id}-${i}`}
                style={{
                  padding: "0.5rem",
                  marginBottom: "0.4rem",
                  border: "1px solid #e8e8e8",
                  borderRadius: 3,
                  background: "#fff",
                }}
              >
                {/* Row 1: rank + source_type + method badge + score */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    flexWrap: "wrap",
                    marginBottom: "0.2rem",
                  }}
                >
                  <span
                    className="text-dim"
                    style={{ fontSize: "0.65rem", fontWeight: 600 }}
                  >
                    #{i + 1}
                  </span>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "0.05rem 0.3rem",
                      borderRadius: 2,
                      fontSize: "0.65rem",
                      background: "#eceff1",
                      color: "#546e7a",
                    }}
                  >
                    {c.source_type}
                  </span>
                  <RetrievalMethodBadge method={c.method} />
                  <span className="text-dim" style={{ fontSize: "0.68rem" }}>
                    Score: {formatScore(c.score)}
                  </span>
                  {locSummary && (
                    <span
                      className="text-dim"
                      style={{
                        fontSize: "0.65rem",
                        marginLeft: "auto",
                        maxWidth: "12rem",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={locSummary}
                    >
                      {locSummary}
                    </span>
                  )}
                </div>

                {/* Row 2: title */}
                <p style={{ fontSize: "0.75rem", fontWeight: 600, margin: "0 0 0.15rem 0" }}>
                  {c.title}
                </p>

                {/* Row 3: snippet */}
                <p
                  style={{
                    fontSize: "0.78rem",
                    lineHeight: 1.5,
                    margin: "0 0 0.2rem 0",
                    color: "#333",
                  }}
                >
                  {c.snippet}
                </p>

                {/* Row 4: matched_terms + chunk_id */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    flexWrap: "wrap",
                  }}
                >
                  {c.matched_terms.length > 0 && (
                    <span className="text-dim" style={{ fontSize: "0.68rem" }}>
                      Matched: {c.matched_terms.join(", ")}
                    </span>
                  )}
                  {c.chunk_id && (
                    <code style={{ fontSize: "0.6rem" }}>{c.chunk_id}</code>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
