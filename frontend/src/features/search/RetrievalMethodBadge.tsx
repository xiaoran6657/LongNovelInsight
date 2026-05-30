const METHOD_COLORS: Record<string, { bg: string; fg: string; border: string }> = {
  fts: { bg: "#e3f2fd", fg: "#1565c0", border: "#90caf9" },
  keyword_fallback: { bg: "#e8f5e9", fg: "#2e7d32", border: "#a5d6a7" },
  structured: { bg: "#f3e5f5", fg: "#7b1fa2", border: "#ce93d8" },
  analysis_output: { bg: "#fff3e0", fg: "#e65100", border: "#ffcc80" },
  semantic_rerank: { bg: "#e0f2f1", fg: "#00695c", border: "#80cbc4" },
};

interface Props {
  method: string;
}

export default function RetrievalMethodBadge({ method }: Props) {
  const colors = METHOD_COLORS[method] ?? {
    bg: "#f5f5f5",
    fg: "#616161",
    border: "#e0e0e0",
  };

  return (
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
      {method}
    </span>
  );
}
