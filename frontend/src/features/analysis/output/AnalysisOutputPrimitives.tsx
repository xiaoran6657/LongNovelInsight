import { formatConfidence } from "./analysisOutputData";

export function ItemConfBadge({ c }: { c: number | null | undefined }) {
  const { text, color } = formatConfidence(c);
  return (
    <span
      style={{
        fontSize: "0.72rem",
        color,
        fontWeight: 600,
        marginLeft: "0.35rem",
      }}
    >
      {text}
    </span>
  );
}

export function EvidenceBlock({ quotes }: { quotes: string[] }) {
  if (quotes.length === 0) return null;
  return (
    <div style={{ marginTop: "0.3rem" }}>
      <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#aaa" }}>Evidence:</span>
      {quotes.map((quote, index) => (
        <blockquote
          key={index}
          style={{
            margin: "0.1rem 0 0.2rem 0",
            padding: "0.15rem 0.5rem",
            borderLeft: "2px solid #ddd",
            fontSize: "0.78rem",
            color: "#777",
            fontStyle: "italic",
          }}
        >
          {quote.length > 250 ? quote.slice(0, 250) + "..." : quote}
        </blockquote>
      ))}
    </div>
  );
}

export function ChunkTags({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: "0.2rem",
        flexWrap: "wrap",
        marginTop: "0.25rem",
      }}
    >
      {ids.map((id) => (
        <span key={id} className="chunk-tag">
          {id.length > 10 ? id.slice(0, 10) + "…" : id}
        </span>
      ))}
    </div>
  );
}
