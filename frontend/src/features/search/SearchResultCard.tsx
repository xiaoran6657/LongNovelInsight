import type { SearchResult } from "../../api/types";

interface Props {
  result: SearchResult;
  onOpenLocator?: (chunkId: string) => void;
}

const METHOD_COLORS: Record<string, { bg: string; fg: string; border: string }> = {
  fts: { bg: "#e3f2fd", fg: "#1565c0", border: "#90caf9" },
  keyword_fallback: { bg: "#e8f5e9", fg: "#2e7d32", border: "#a5d6a7" },
};

function formatScore(score: number): string {
  return score.toFixed(2);
}

export default function SearchResultCard({ result, onOpenLocator }: Props) {
  const colors = METHOD_COLORS[result.method] ?? {
    bg: "#f5f5f5",
    fg: "#616161",
    border: "#e0e0e0",
  };

  const chapterLabel =
    result.chapter_index != null ? `Ch.${result.chapter_index + 1}` : null;
  const chunkLabel = `#${result.chunk_index}`;
  const locatorDetail = [chapterLabel, chunkLabel, result.title]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      style={{
        padding: "0.5rem",
        marginBottom: "0.5rem",
        border: "1px solid #eee",
        borderRadius: 4,
        background: "#fafafa",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          flexWrap: "wrap",
          marginBottom: "0.25rem",
        }}
      >
        <span
          style={{
            display: "inline-block",
            padding: "0.1rem 0.4rem",
            borderRadius: 3,
            fontSize: "0.7rem",
            fontWeight: 600,
            background: colors.bg,
            color: colors.fg,
            border: `1px solid ${colors.border}`,
          }}
        >
          {result.method}
        </span>
        <span className="text-dim" style={{ fontSize: "0.7rem" }}>
          Score: {formatScore(result.score)}
        </span>
        {onOpenLocator && (
          <button
            onClick={() => onOpenLocator(result.chunk_id)}
            style={{
              fontSize: "0.68rem",
              padding: "0.1rem 0.4rem",
              marginLeft: "auto",
            }}
          >
            Open
          </button>
        )}
      </div>

      <p style={{ fontSize: "0.8rem", margin: "0.25rem 0", lineHeight: 1.5 }}>
        {result.snippet}
      </p>

      <p className="text-dim" style={{ fontSize: "0.7rem", margin: 0 }}>
        {locatorDetail}
      </p>
    </div>
  );
}
