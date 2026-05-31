import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getSimilarScenes } from "../../api/entities";
import { getChunkLocator } from "../../api/search";
import type { SimilarScenesResponse, LocatorResponse } from "../../api/types";
import SourceLocatorBadge from "../topic/SourceLocatorBadge";

interface Props {
  topicId: string;
}

type Mode = "query" | "chunk";

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

export default function SimilarScenesPanel({ topicId }: Props) {
  const [mode, setMode] = useState<Mode>("query");
  const [queryInput, setQueryInput] = useState("");
  const [chunkIdInput, setChunkIdInput] = useState("");
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  const searchMut = useMutation({
    mutationFn: (): Promise<SimilarScenesResponse> => {
      if (mode === "query") {
        return getSimilarScenes(topicId, { query: queryInput.trim() });
      } else {
        return getSimilarScenes(topicId, { chunk_id: chunkIdInput.trim() });
      }
    },
  });

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

  function handleSubmit() {
    if (searchMut.isPending) return;
    if (mode === "query" && !queryInput.trim()) return;
    if (mode === "chunk" && !chunkIdInput.trim()) return;
    setSelectedChunkId(null);
    searchMut.mutate();
  }

  function switchMode(newMode: Mode) {
    setMode(newMode);
    setSelectedChunkId(null);
    searchMut.reset();
  }

  const response = searchMut.data;
  const hasSearched = searchMut.isSuccess || searchMut.isError;
  const is422 =
    searchMut.isError &&
    searchMut.error instanceof Error &&
    searchMut.error.message.includes("422");
  const is404 =
    searchMut.isError &&
    searchMut.error instanceof Error &&
    searchMut.error.message.includes("404");

  return (
    <div className="card">
      <h3>Similar Scenes</h3>
      <p className="text-dim" style={{ fontSize: "0.78rem", marginBottom: "0.5rem" }}>
        Find scenes similar to a query or a specific chunk. Similarity is based
        on lexical overlap and shared entities (atoms).
      </p>

      {/* ── Mode tabs ── */}
      <div style={{ display: "flex", gap: 0, marginBottom: "0.5rem" }}>
        {(["query", "chunk"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            disabled={searchMut.isPending}
            style={{
              fontSize: "0.75rem",
              padding: "0.2rem 0.6rem",
              borderRadius: mode === m ? 3 : 0,
              border:
                mode === m ? "1px solid #1565c0" : "1px solid #e0e0e0",
              background: mode === m ? "#e3f2fd" : "#fff",
              color: mode === m ? "#1565c0" : "#666",
              fontWeight: mode === m ? 600 : 400,
              cursor: searchMut.isPending ? "not-allowed" : "pointer",
            }}
          >
            {m === "query" ? "By Query" : "By Chunk ID"}
          </button>
        ))}
      </div>

      {/* ── Input row ── */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.25rem" }}>
        <input
          type="text"
          value={mode === "query" ? queryInput : chunkIdInput}
          onChange={(e) => {
            if (mode === "query") setQueryInput(e.target.value);
            else setChunkIdInput(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder={
            mode === "query"
              ? "Describe a scene to find similar ones..."
              : "Paste a chunk ID..."
          }
          style={{ flex: 1 }}
        />
        <button
          onClick={handleSubmit}
          disabled={
            searchMut.isPending ||
            (mode === "query" ? !queryInput.trim() : !chunkIdInput.trim())
          }
        >
          {searchMut.isPending ? "Searching..." : "Find"}
        </button>
      </div>

      {/* ── Idle ── */}
      {!hasSearched && !searchMut.isPending && (
        <p className="text-dim" style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}>
          {mode === "query"
            ? "Enter a phrase or scene description to find similar passages."
            : "Enter a chunk ID from search results or analysis outputs."}
        </p>
      )}

      {/* ── Loading ── */}
      {searchMut.isPending && (
        <p className="text-dim" style={{ marginTop: "0.5rem" }}>
          Searching for similar scenes...
        </p>
      )}

      {/* ── 404 error ── */}
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
            {mode === "chunk"
              ? "Chunk not found"
              : "Topic not found or endpoint unavailable"}
          </p>
          <p>
            {mode === "chunk"
              ? "The provided chunk ID does not exist in this topic."
              : "Run analysis first and verify the topic exists."}
          </p>
        </div>
      )}

      {/* ── 422 error ── */}
      {is422 && (
        <p className="field-error" style={{ marginTop: "0.5rem" }}>
          {searchMut.error instanceof Error
            ? searchMut.error.message
            : "Invalid request"}
        </p>
      )}

      {/* ── Other error ── */}
      {searchMut.isError && !is404 && !is422 && (
        <p className="field-error" style={{ marginTop: "0.5rem" }}>
          {searchMut.error instanceof Error
            ? searchMut.error.message
            : "Failed to find similar scenes"}
        </p>
      )}

      {/* ── Empty ── */}
      {hasSearched && !searchMut.isPending && response && response.results.length === 0 && (
        <p className="text-dim" style={{ marginTop: "0.5rem" }}>
          No similar scenes found.
        </p>
      )}

      {/* ── Results ── */}
      {response && response.results.length > 0 && (
        <div style={{ marginTop: "0.75rem" }}>
          <p
            style={{
              fontSize: "0.7rem",
              fontWeight: 600,
              color: "#888",
              textTransform: "uppercase",
              letterSpacing: "0.03em",
              marginBottom: "0.35rem",
            }}
          >
            Results ({response.results.length})
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            {response.results.map((item) => {
              const locSum = locatorSummary(item.locator);
              const isSelected = selectedChunkId === item.chunk_id;
              return (
                <div
                  key={item.chunk_id}
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #e8e8e8",
                    borderRadius: 4,
                    background: "#fafafa",
                    fontSize: "0.78rem",
                  }}
                >
                  {/* Header row */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      flexWrap: "wrap",
                      marginBottom: "0.2rem",
                    }}
                  >
                    {item.chapter_index != null && (
                      <span style={{ fontWeight: 600, fontSize: "0.73rem" }}>
                        Ch.{item.chapter_index + 1}
                      </span>
                    )}
                    <span className="text-dim" style={{ fontSize: "0.7rem" }}>
                      #{item.chunk_index}
                    </span>
                    <span
                      style={{
                        fontSize: "0.65rem",
                        padding: "0.05rem 0.3rem",
                        borderRadius: 2,
                        background: "#fff3e0",
                        color: "#e65100",
                        fontWeight: 600,
                      }}
                    >
                      Score: {formatScore(item.score)}
                    </span>
                    {item.locator && (
                      <SourceLocatorBadge
                        sourceLocatorJson={JSON.stringify(item.locator)}
                        fileType={undefined}
                        chapterIndex={item.chapter_index ?? undefined}
                        chunkIndex={item.chunk_index}
                      />
                    )}
                    {locSum && (
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
                        title={locSum}
                      >
                        {locSum}
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

                  {/* Snippet */}
                  <p
                    style={{
                      margin: "0 0 0.2rem 0",
                      lineHeight: 1.5,
                      color: "#444",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {item.snippet}
                  </p>

                  {/* Open source */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <code style={{ fontSize: "0.58rem" }}>{item.chunk_id}</code>
                    <button
                      onClick={() =>
                        setSelectedChunkId(isSelected ? null : item.chunk_id)
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

                  {/* Inline locator detail */}
                  {isSelected && (
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
  chunkId,
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
        <p style={{ margin: "0 0 0.3rem 0" }}>
          <span className="text-dim">Chunk ID:</span>{" "}
          <code style={{ fontSize: "0.7rem" }}>{chunkId}</code>
        </p>
      </div>

      <div
        style={{
          padding: "0.35rem",
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
