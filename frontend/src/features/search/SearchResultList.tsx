import type { SearchResult } from "../../api/types";
import SearchResultCard from "./SearchResultCard";

interface Props {
  results: SearchResult[];
  onOpenLocator?: (chunkId: string) => void;
}

export default function SearchResultList({ results, onOpenLocator }: Props) {
  if (results.length === 0) return null;

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <p className="text-dim" style={{ fontSize: "0.78rem", marginBottom: "0.5rem" }}>
        {results.length} result{results.length !== 1 ? "s" : ""}
      </p>
      {results.map((r) => (
        <SearchResultCard
          key={r.chunk_id}
          result={r}
          onOpenLocator={onOpenLocator}
        />
      ))}
    </div>
  );
}
