import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntityEvidence } from "../../api/entities";
import type { EntityEvidenceResponse } from "../../api/types";
import SourceLocatorBadge from "../topic/SourceLocatorBadge";
import RetrievalMethodBadge from "../search/RetrievalMethodBadge";

interface Props {
  topicId: string;
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

const LABEL_STYLE: React.CSSProperties = {
  fontSize: "0.63rem",
  fontWeight: 600,
  color: "#888",
  textTransform: "uppercase" as const,
  letterSpacing: "0.03em",
};

export default function EntityEvidencePanel({ topicId }: Props) {
  const [entityInput, setEntityInput] = useState("");
  const [searchId, setSearchId] = useState<string | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["entity-evidence", topicId, searchId],
    queryFn: () => getEntityEvidence(topicId, searchId!),
    enabled: searchId != null,
    retry: false,
  });

  function handleSearch() {
    const trimmed = entityInput.trim();
    if (!trimmed) return;
    setSearchId(trimmed);
  }

  const is404 =
    isError && error instanceof Error && error.message.includes("404");

  return (
    <div className="card">
      <h3>Entity Evidence</h3>
      <p className="text-dim" style={{ fontSize: "0.78rem", marginBottom: "0.5rem" }}>
        Look up evidence for a character, event, location, or other entity by its
        stable ID. Entity IDs can be found in analysis outputs.
      </p>

      {/* ── Input row ── */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input
          type="text"
          value={entityInput}
          onChange={(e) => setEntityInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSearch();
          }}
          placeholder="e.g. char_liubei, xiao_yan, 刘备..."
          style={{ flex: 1 }}
        />
        <button onClick={handleSearch} disabled={isLoading || !entityInput.trim()}>
          {isLoading ? "Loading..." : "Lookup"}
        </button>
      </div>

      {/* ── Idle ── */}
      {!searchId && !isLoading && (
        <p className="text-dim" style={{ fontSize: "0.75rem" }}>
          Enter an entity ID above. Requires analysis to have been run (atoms
          come from the analysis pipeline).
        </p>
      )}

      {/* ── Loading ── */}
      {isLoading && (
        <p className="text-dim" style={{ marginTop: "0.5rem" }}>
          Loading evidence...
        </p>
      )}

      {/* ── 404 — topic not found or endpoint unavailable ── */}
      {is404 && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem 0.75rem",
            border: "1px solid #ffe0b2",
            borderRadius: 4,
            background: "#fff8e1",
            fontSize: "0.78rem",
            color: "#e65100",
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: "0.2rem" }}>
            Topic not found or endpoint unavailable
          </p>
          <p>
            The entity evidence endpoint may not be available. Run analysis first
            and verify the topic exists. Entity IDs use stable_id or canonical_name
            (e.g.{" "}
            <code style={{ fontSize: "0.75rem" }}>char_liubei</code>,{" "}
            <code style={{ fontSize: "0.75rem" }}>xiao_yan</code>,{" "}
            <code style={{ fontSize: "0.75rem" }}>刘备</code>).
            If the entity is valid but not found, check the empty state below.
          </p>
        </div>
      )}

      {/* ── Other error ── */}
      {isError && !is404 && (
        <p className="field-error" style={{ marginTop: "0.5rem" }}>
          {error instanceof Error ? error.message : "Failed to load evidence"}
        </p>
      )}

      {/* ── Results ── */}
      {data && <EvidenceResults data={data} />}
    </div>
  );
}

/* ── Results display ── */

function EvidenceResults({ data }: { data: EntityEvidenceResponse }) {
  const { atoms, chunks, outputs } = data;

  if (atoms.length === 0 && chunks.length === 0 && outputs.length === 0) {
    return (
      <p className="text-dim" style={{ marginTop: "0.5rem" }}>
        No evidence found for this entity.
      </p>
    );
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      {/* Entity header */}
      {data.canonical_name && (
        <p style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: "0.5rem" }}>
          {data.canonical_name}{" "}
          <code style={{ fontSize: "0.7rem", fontWeight: 400 }}>
            {data.entity_id}
          </code>
        </p>
      )}

      {/* ── Atoms ── */}
      {atoms.length > 0 && (
        <div style={{ marginBottom: "0.75rem" }}>
          <p style={LABEL_STYLE}>
            Atoms ({atoms.length})
          </p>
          {atoms.map((atom) => (
            <div
              key={atom.id}
              style={{
                padding: "0.5rem",
                marginBottom: "0.35rem",
                border: "1px solid #e8e8e8",
                borderRadius: 4,
                background: "#fafafa",
                fontSize: "0.78rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  flexWrap: "wrap",
                  marginBottom: "0.2rem",
                }}
              >
                <RetrievalMethodBadge method={atom.atom_type} />
                {atom.canonical_name && (
                  <span style={{ fontWeight: 600, fontSize: "0.8rem" }}>
                    {atom.canonical_name}
                  </span>
                )}
                {atom.title && (
                  <span className="text-dim" style={{ fontSize: "0.7rem" }}>
                    {atom.title}
                  </span>
                )}
                {atom.confidence != null && (
                  <span className="text-dim" style={{ fontSize: "0.68rem" }}>
                    conf: {atom.confidence.toFixed(2)}
                  </span>
                )}
                {atom.chapter_index != null && (
                  <span className="text-dim" style={{ fontSize: "0.68rem", marginLeft: "auto" }}>
                    Ch.{atom.chapter_index + 1}
                    {atom.chunk_index != null && ` #${atom.chunk_index}`}
                  </span>
                )}
              </div>
              {atom.summary && (
                <p style={{ margin: "0 0 0.25rem 0", lineHeight: 1.5, color: "#444" }}>
                  {atom.summary}
                </p>
              )}
              {atom.evidence_quotes && atom.evidence_quotes.length > 0 && (
                <div
                  style={{
                    padding: "0.35rem 0.5rem",
                    background: "#fff",
                    border: "1px solid #f0f0f0",
                    borderRadius: 3,
                    fontSize: "0.73rem",
                    color: "#666",
                    maxHeight: 140,
                    overflowY: "auto",
                  }}
                >
                  {atom.evidence_quotes.map((q, qi) => (
                    <p
                      key={qi}
                      style={{
                        margin: qi > 0 ? "0.3rem 0 0 0" : 0,
                        fontStyle: "italic",
                      }}
                    >
                      &ldquo;{q}&rdquo;
                    </p>
                  ))}
                </div>
              )}
              <p style={{ margin: "0.15rem 0 0 0" }}>
                <code style={{ fontSize: "0.6rem" }}>{atom.stable_id}</code>
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ── Evidence Chunks ── */}
      {chunks.length > 0 && (
        <div style={{ marginBottom: "0.75rem" }}>
          <p style={LABEL_STYLE}>
            Source Chunks ({chunks.length})
          </p>
          {chunks.map((chunk) => {
            const locSum = locatorSummary(chunk.locator);
            return (
              <div
                key={chunk.id}
                style={{
                  padding: "0.5rem",
                  marginBottom: "0.35rem",
                  border: "1px solid #c8e6c9",
                  borderRadius: 4,
                  background: "#f1f8e9",
                  fontSize: "0.78rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    flexWrap: "wrap",
                    marginBottom: "0.2rem",
                  }}
                >
                  {chunk.chapter_index != null && (
                    <span style={{ fontWeight: 600, fontSize: "0.73rem" }}>
                      Ch.{chunk.chapter_index + 1}
                    </span>
                  )}
                  <span className="text-dim" style={{ fontSize: "0.7rem" }}>
                    #{chunk.chunk_index}
                  </span>
                  {chunk.locator && (
                    <SourceLocatorBadge
                      sourceLocatorJson={JSON.stringify(chunk.locator)}
                      fileType={undefined}
                      chapterIndex={chunk.chapter_index ?? undefined}
                      chunkIndex={chunk.chunk_index}
                    />
                  )}
                  {locSum && (
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
                      title={locSum}
                    >
                      {locSum}
                    </span>
                  )}
                </div>
                <p
                  style={{
                    margin: 0,
                    lineHeight: 1.5,
                    color: "#444",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {chunk.excerpt}
                </p>
                <p style={{ margin: "0.1rem 0 0 0" }}>
                  <code style={{ fontSize: "0.6rem" }}>{chunk.id}</code>
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Analysis Outputs ── */}
      {outputs.length > 0 && (
        <div>
          <p style={LABEL_STYLE}>
            Related Outputs ({outputs.length})
          </p>
          {outputs.map((out) => (
            <div
              key={out.id}
              style={{
                padding: "0.5rem",
                marginBottom: "0.35rem",
                border: "1px solid #e3f2fd",
                borderRadius: 4,
                background: "#e8eaf6",
                fontSize: "0.78rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  flexWrap: "wrap",
                  marginBottom: "0.15rem",
                }}
              >
                <RetrievalMethodBadge method={out.output_type} />
                <span style={{ fontWeight: 600, fontSize: "0.78rem" }}>
                  {out.title}
                </span>
              </div>
              <p
                style={{
                  margin: 0,
                  lineHeight: 1.5,
                  color: "#444",
                  whiteSpace: "pre-wrap",
                }}
              >
                {out.excerpt}
              </p>
              <p style={{ margin: "0.1rem 0 0 0" }}>
                <code style={{ fontSize: "0.6rem" }}>{out.id}</code>
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
