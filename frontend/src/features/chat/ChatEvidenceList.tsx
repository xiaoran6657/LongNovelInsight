import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getChunkLocator } from "../../api/search";
import type {
  ParsedEvidence,
  StructuredEvidenceItem,
  LocatorResponse,
} from "../../api/types";
import RetrievalMethodBadge from "../search/RetrievalMethodBadge";

/** Safely parse and normalize evidence_json into ParsedEvidence. */
export function normalizeEvidence(raw: string | null): ParsedEvidence {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    // Accept either all-strings (legacy) or all-objects (structured).
    // Mixed arrays default to legacy rendering.
    return parsed as ParsedEvidence;
  } catch {
    return null;
  }
}

interface Props {
  topicId: string;
  evidence: ParsedEvidence;
  uncertainty: string | null;
}

function locatorSummary(loc: Record<string, unknown> | null): string | null {
  if (!loc) return null;
  const href = loc.href ?? (loc as Record<string, unknown>).source_href;
  const parts: string[] = [];
  if (typeof loc.chapter_title === "string") parts.push(String(loc.chapter_title));
  if (typeof href === "string") {
    const segs = href.split("/");
    parts.push(segs[segs.length - 1] || href);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function hrefFromLocator(loc: Record<string, unknown>): string | null {
  const h = loc.href ?? (loc as Record<string, unknown>).source_href;
  return typeof h === "string" ? h : null;
}

function abbreviateHref(href: string): string {
  const parts = href.split("/");
  return parts[parts.length - 1] || href;
}

function formatScore(score: number): string {
  return score.toFixed(3);
}

export default function ChatEvidenceList({
  topicId,
  evidence,
  uncertainty,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  const items = Array.isArray(evidence) ? evidence : [];
  const hasItems = items.length > 0;

  // Locator fetch for source opening
  const {
    data: locatorData,
    isLoading: locatorLoading,
    isError: locatorError,
  } = useQuery({
    queryKey: ["chunk-locator", topicId, selectedChunkId],
    queryFn: () => getChunkLocator(topicId, selectedChunkId!),
    enabled: selectedChunkId != null,
    retry: false,
  });

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
            const isSelected = selectedChunkId === item.chunk_id;
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

                {/* Chunk ID + Open source */}
                {item.chunk_id && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      marginTop: "0.15rem",
                    }}
                  >
                    <code style={{ fontSize: "0.58rem" }}>{item.chunk_id}</code>
                    <button
                      onClick={() =>
                        setSelectedChunkId(
                          isSelected ? null : item.chunk_id
                        )
                      }
                      style={{
                        fontSize: "0.62rem",
                        padding: "0.08rem 0.35rem",
                        ...(isSelected
                          ? {
                              background: "#e3f2fd",
                              borderColor: "#90caf9",
                              color: "#1565c0",
                            }
                          : {}),
                      }}
                    >
                      {isSelected ? "Close source" : "Open source"}
                    </button>
                  </div>
                )}

                {/* Inline locator detail */}
                {isSelected && item.chunk_id && (
                  <LocatorDetail
                    data={locatorData ?? null}
                    isLoading={locatorLoading}
                    isError={locatorError}
                    chunkId={item.chunk_id}
                    onClose={() => setSelectedChunkId(null)}
                  />
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

/* ── Inline chunk locator detail ── */

function LocatorDetail({
  data,
  isLoading,
  isError,
  onClose,
}: {
  data: LocatorResponse | null;
  isLoading: boolean;
  isError: boolean;
  chunkId: string;
  onClose: () => void;
}) {
  if (isLoading) {
    return (
      <p className="text-dim" style={{ marginTop: "0.4rem", fontSize: "0.68rem" }}>
        Loading locator...
      </p>
    );
  }

  if (isError || !data) {
    return (
      <p className="field-error" style={{ marginTop: "0.4rem", fontSize: "0.7rem" }}>
        Failed to load chunk locator.
        <button
          onClick={onClose}
          style={{ fontSize: "0.6rem", marginLeft: "0.4rem" }}
        >
          Dismiss
        </button>
      </p>
    );
  }

  const href = hrefFromLocator(data.locator);
  const chapterTitle =
    typeof data.locator.chapter_title === "string"
      ? data.locator.chapter_title
      : null;

  return (
    <div
      style={{
        marginTop: "0.4rem",
        padding: "0.5rem",
        border: "1px solid #c8e6c9",
        borderRadius: 3,
        background: "#f1f8e9",
        fontSize: "0.7rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.25rem",
        }}
      >
        <strong style={{ fontSize: "0.72rem" }}>Source Locator</strong>
        <button onClick={onClose} style={{ fontSize: "0.6rem", padding: "0.08rem 0.35rem" }}>
          Close
        </button>
      </div>

      <div style={{ lineHeight: 1.5 }}>
        <p style={{ margin: "0 0 0.1rem 0" }}>
          <span className="text-dim">Chapter:</span>{" "}
          {data.chapter_index != null ? data.chapter_index + 1 : "—"}
          {chapterTitle && (
            <span style={{ marginLeft: "0.25rem" }}>{chapterTitle}</span>
          )}
        </p>
        <p style={{ margin: "0 0 0.1rem 0" }}>
          <span className="text-dim">Chunk:</span> #{data.chunk_index}
        </p>
        {href && (
          <p style={{ margin: "0 0 0.1rem 0" }}>
            <span className="text-dim">Source:</span> {abbreviateHref(href)}
            <span
              className="text-dim"
              style={{ fontSize: "0.6rem", marginLeft: "0.25rem" }}
              title={href}
            >
              (hover for full path)
            </span>
          </p>
        )}
      </div>

      <div
        style={{
          padding: "0.35rem",
          marginTop: "0.3rem",
          background: "#fff",
          border: "1px solid #e0e0e0",
          borderRadius: 3,
          fontSize: "0.73rem",
          lineHeight: 1.5,
          maxHeight: 160,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
        }}
      >
        {data.excerpt}
      </div>
    </div>
  );
}
