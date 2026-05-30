import { useState, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { searchChunks, getChunkLocator } from "../../api/search";
import type { SearchMethod, SearchResponse, LocatorResponse } from "../../api/types";
import SearchResultList from "./SearchResultList";
import RetrievalDebugDrawer from "./RetrievalDebugDrawer";

interface Props {
  topicId: string;
}

const ALL_METHODS: { key: SearchMethod; label: string }[] = [
  { key: "fts", label: "FTS" },
  { key: "keyword_fallback", label: "Keyword Fallback" },
];

function hrefFromLocator(loc: Record<string, unknown>): string | null {
  const h = loc.href ?? loc.source_href;
  return typeof h === "string" ? h : null;
}

function abbreviateHref(href: string): string {
  const parts = href.split("/");
  return parts[parts.length - 1] || href;
}

export default function TopicSearchPanel({ topicId }: Props) {
  const [query, setQuery] = useState("");
  const [methods, setMethods] = useState<Set<SearchMethod>>(
    new Set(["fts", "keyword_fallback"])
  );
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const [showDebugDrawer, setShowDebugDrawer] = useState(false);
  const submittedQueryRef = useRef("");

  const searchMut = useMutation({
    mutationFn: (q: string) =>
      searchChunks(topicId, {
        query: q,
        limit: 20,
        methods: [...methods],
      }),
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

  function toggleMethod(m: SearchMethod) {
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

  function handleSubmit() {
    const trimmed = query.trim();
    if (!trimmed || searchMut.isPending) return;
    setSelectedChunkId(null);
    setShowDebugDrawer(false);
    submittedQueryRef.current = trimmed;
    searchMut.mutate(trimmed);
  }

  function handleOpenLocator(chunkId: string) {
    setSelectedChunkId(chunkId);
  }

  const response: SearchResponse | undefined = searchMut.data;
  const hasSearched = searchMut.isSuccess || searchMut.isError;

  return (
    <div className="card">
      <h3>Search</h3>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder="Search within this topic..."
          style={{ flex: 1 }}
        />
        <button onClick={handleSubmit} disabled={searchMut.isPending}>
          {searchMut.isPending ? "Searching..." : "Search"}
        </button>
        {hasSearched && !searchMut.isPending && (
          <button
            onClick={() => setShowDebugDrawer(!showDebugDrawer)}
            disabled={!submittedQueryRef.current}
            style={{
              fontSize: "0.8rem",
              ...(showDebugDrawer
                ? { background: "#e3f2fd", borderColor: "#90caf9", color: "#1565c0" }
                : {}),
            }}
          >
            {showDebugDrawer ? "Hide Debug" : "Debug retrieval"}
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.25rem" }}>
        {ALL_METHODS.map(({ key, label }) => (
          <label
            key={key}
            style={{ fontSize: "0.8rem", cursor: "pointer" }}
          >
            <input
              type="checkbox"
              checked={methods.has(key)}
              onChange={() => toggleMethod(key)}
              style={{ marginRight: "0.25rem" }}
            />
            {label}
          </label>
        ))}
      </div>

      {/* Loading state */}
      {searchMut.isPending && (
        <p className="text-dim" style={{ marginTop: "0.5rem" }}>
          Searching...
        </p>
      )}

      {/* Error state */}
      {searchMut.isError && (
        <p className="field-error" style={{ marginTop: "0.5rem" }}>
          {searchMut.error instanceof Error
            ? searchMut.error.message
            : "Search failed"}
        </p>
      )}

      {/* Empty state */}
      {hasSearched && !searchMut.isPending && response && response.results.length === 0 && (
        <p className="text-dim" style={{ marginTop: "0.5rem" }}>
          No results found.
        </p>
      )}

      {/* Results */}
      {response && response.results.length > 0 && (
        <SearchResultList
          results={response.results}
          onOpenLocator={handleOpenLocator}
        />
      )}

      {/* Locator detail for selected chunk */}
      {selectedChunkId && (
        <LocatorDetail
          data={locatorData ?? null}
          isLoading={locatorLoading}
          isError={locatorError}
          onClose={() => setSelectedChunkId(null)}
        />
      )}

      {showDebugDrawer && submittedQueryRef.current && (
        <RetrievalDebugDrawer
          topicId={topicId}
          query={submittedQueryRef.current}
          onClose={() => setShowDebugDrawer(false)}
        />
      )}
    </div>
  );
}

function LocatorDetail({
  data,
  isLoading,
  isError,
  onClose,
}: {
  data: LocatorResponse | null;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
}) {
  if (isLoading) {
    return (
      <p className="text-dim" style={{ marginTop: "0.5rem" }}>
        Loading locator...
      </p>
    );
  }

  if (isError || !data) {
    return (
      <p className="field-error" style={{ marginTop: "0.5rem" }}>
        Failed to load chunk locator.
        <button
          onClick={onClose}
          style={{ fontSize: "0.7rem", marginLeft: "0.5rem" }}
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
        marginTop: "0.75rem",
        padding: "0.75rem",
        border: "1px solid #c8e6c9",
        borderRadius: 4,
        background: "#f1f8e9",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.4rem",
        }}
      >
        <strong style={{ fontSize: "0.82rem" }}>Chunk Locator</strong>
        <button onClick={onClose} style={{ fontSize: "0.68rem" }}>
          Close
        </button>
      </div>

      <div style={{ fontSize: "0.78rem", lineHeight: 1.6 }}>
        <p style={{ margin: "0 0 0.2rem 0" }}>
          <span className="text-dim">Chapter:</span>{" "}
          {data.chapter_index != null ? data.chapter_index + 1 : "—"}
          {chapterTitle && (
            <span style={{ marginLeft: "0.3rem" }}>{chapterTitle}</span>
          )}
        </p>
        <p style={{ margin: "0 0 0.2rem 0" }}>
          <span className="text-dim">Chunk:</span> #{data.chunk_index}
        </p>
        {href && (
          <p style={{ margin: "0 0 0.2rem 0" }}>
            <span className="text-dim">Source:</span> {abbreviateHref(href)}
            <span
              className="text-dim"
              style={{ fontSize: "0.65rem", marginLeft: "0.3rem" }}
              title={href}
            >
              (hover for full path)
            </span>
          </p>
        )}
        <p style={{ margin: "0 0 0.3rem 0" }}>
          <span className="text-dim">Chunk ID:</span>{" "}
          <code style={{ fontSize: "0.7rem" }}>{data.chunk_id}</code>
        </p>
      </div>

      <div
        style={{
          padding: "0.5rem",
          background: "#fff",
          border: "1px solid #e0e0e0",
          borderRadius: 3,
          fontSize: "0.8rem",
          lineHeight: 1.5,
          maxHeight: 200,
          overflowY: "auto",
        }}
      >
        {data.excerpt}
      </div>
    </div>
  );
}
