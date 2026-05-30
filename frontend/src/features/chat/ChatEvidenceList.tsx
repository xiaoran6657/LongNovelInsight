import { useState } from "react";
import type { ParsedEvidence, StructuredEvidenceItem } from "../../api/types";
import RetrievalMethodBadge from "../search/RetrievalMethodBadge";

interface Props {
  evidence: ParsedEvidence;
  uncertainty: string | null;
}

function locatorSummary(loc: Record<string, unknown> | null): string | null {
  if (!loc) return null;
  const href = loc.href ?? (loc as Record<string, unknown>).source_href;
  const parts: string[] = [];
  if (typeof href === "string") {
    const segs = href.split("/");
    parts.push(segs[segs.length - 1] || href);
  }
  if (typeof loc.chapter_title === "string") parts.push(loc.chapter_title);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function formatScore(score: number): string {
  return score.toFixed(3);
}

export default function ChatEvidenceList({ evidence, uncertainty }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const items = Array.isArray(evidence) ? evidence : [];
  const hasItems = items.length > 0;

  // No evidence at all
  if (!hasItems) {
    if (uncertainty) {
      return (
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
          <p style={{ fontWeight: 600, marginBottom: "0.15rem" }}>
            No evidence — response may be uncertain
          </p>
          <p>{uncertainty}</p>
        </div>
      );
    }
    return (
      <div
        style={{
          marginTop: "0.35rem",
          fontSize: "0.7rem",
          color: "#999",
        }}
      >
        No evidence cited
      </div>
    );
  }

  const isLegacy = typeof items[0] === "string";

  return (
    <div
      style={{
        marginTop: "0.5rem",
        borderTop: isLegacy ? "1px solid #ddd" : "1px solid #c8e6c9",
        paddingTop: "0.35rem",
        fontSize: "0.75rem",
        color: "#555",
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: collapsed ? 0 : "0.25rem",
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <p style={{ fontWeight: 600, margin: 0, fontSize: "0.73rem" }}>
          {isLegacy ? "Evidence (legacy)" : "Evidence"} ({items.length})
        </p>
        <span style={{ fontSize: "0.65rem", color: "#999" }}>
          {collapsed ? "▶" : "▼"}
        </span>
      </div>

      {collapsed && (
        <p className="text-dim" style={{ fontSize: "0.68rem", margin: 0 }}>
          Click to expand
        </p>
      )}

      {/* ── Legacy string evidence ── */}
      {!collapsed && isLegacy && (
        <ul style={{ paddingLeft: "1.2rem", margin: 0 }}>
          {(items as string[]).map((text, i) => (
            <li key={i} style={{ marginBottom: "0.15rem", fontSize: "0.75rem" }}>
              {text}
            </li>
          ))}
        </ul>
      )}

      {/* ── Structured evidence cards ── */}
      {!collapsed && !isLegacy && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          {(items as StructuredEvidenceItem[]).map((item, i) => {
            const locSummary = locatorSummary(item.locator);
            return (
              <div
                key={`${item.source_id}-${i}`}
                style={{
                  padding: "0.4rem 0.5rem",
                  border: "1px solid #e8e8e8",
                  borderRadius: 4,
                  background: "#fafafa",
                }}
              >
                {/* Badge row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    flexWrap: "wrap",
                    marginBottom: "0.2rem",
                  }}
                >
                  <span
                    style={{
                      display: "inline-block",
                      padding: "0.05rem 0.3rem",
                      borderRadius: 2,
                      fontSize: "0.63rem",
                      fontWeight: 600,
                      background: "#eceff1",
                      color: "#546e7a",
                      textTransform: "uppercase",
                    }}
                  >
                    {item.source_type}
                  </span>
                  {item.method && (
                    <RetrievalMethodBadge method={item.method} />
                  )}
                  {item.score != null && (
                    <span className="text-dim" style={{ fontSize: "0.65rem" }}>
                      Score: {formatScore(item.score)}
                    </span>
                  )}
                  {locSummary && (
                    <span
                      className="text-dim"
                      style={{
                        fontSize: "0.63rem",
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

                {/* Title */}
                {item.title && (
                  <p
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      margin: "0 0 0.15rem 0",
                      color: "#333",
                    }}
                  >
                    {item.title}
                  </p>
                )}

                {/* Text snippet */}
                <p
                  style={{
                    fontSize: "0.78rem",
                    lineHeight: 1.5,
                    margin: 0,
                    color: "#444",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {item.text}
                </p>

                {/* Chunk ID */}
                {item.chunk_id && (
                  <p style={{ margin: "0.15rem 0 0 0" }}>
                    <code style={{ fontSize: "0.58rem" }}>
                      {item.chunk_id}
                    </code>
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Uncertainty ── */}
      {uncertainty && (
        <div
          style={{
            marginTop: "0.35rem",
            borderTop: "1px solid #fcd34d",
            paddingTop: "0.25rem",
            fontSize: "0.7rem",
            color: "#92400e",
            fontStyle: "italic",
          }}
        >
          {uncertainty}
        </div>
      )}
    </div>
  );
}
