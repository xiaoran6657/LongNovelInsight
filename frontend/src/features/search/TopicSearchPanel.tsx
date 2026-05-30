import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { searchChunks } from "../../api/search";
import type { SearchMethod, SearchResponse } from "../../api/types";
import SearchResultList from "./SearchResultList";

interface Props {
  topicId: string;
  onOpenLocator?: (chunkId: string) => void;
}

const ALL_METHODS: { key: SearchMethod; label: string }[] = [
  { key: "fts", label: "FTS" },
  { key: "keyword_fallback", label: "Keyword Fallback" },
];

export default function TopicSearchPanel({ topicId, onOpenLocator }: Props) {
  const [query, setQuery] = useState("");
  const [methods, setMethods] = useState<Set<SearchMethod>>(
    new Set(["fts", "keyword_fallback"])
  );

  const searchMut = useMutation({
    mutationFn: (q: string) =>
      searchChunks(topicId, {
        query: q,
        limit: 20,
        methods: [...methods],
      }),
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
    searchMut.mutate(trimmed);
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
          onOpenLocator={onOpenLocator}
        />
      )}
    </div>
  );
}
