interface Props {
  selectedChunks: number;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  note: string;
}

function fmt(n: number): string {
  return n.toLocaleString();
}

export default function AnalysisCostProjection({ selectedChunks, estimatedInputTokens, estimatedOutputTokens, note }: Props) {
  const total = estimatedInputTokens + estimatedOutputTokens;

  return (
    <div className="card" style={{ fontSize: "0.85rem", background: "#f9fbe7", border: "1px solid #dcedc8" }}>
      <h3>Cost Estimate</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem", marginBottom: "0.5rem" }}>
        <div><strong>Chunks:</strong> {selectedChunks}</div>
        <div><strong>Total tokens:</strong> ~{fmt(total)}</div>
        <div><strong>Input tokens:</strong> ~{fmt(estimatedInputTokens)}</div>
        <div><strong>Output tokens:</strong> ~{fmt(estimatedOutputTokens)}</div>
      </div>
      <p className="text-dim" style={{ fontSize: "0.75rem", lineHeight: 1.5 }}>
        {note}
      </p>
      <p className="text-dim" style={{ fontSize: "0.72rem", marginTop: "0.35rem" }}>
        Estimated API usage, includes retry risk buffer. Actual usage depends on model, prompt, and provider.
        Provider dashboard may be higher if failed/timeout attempts incur server-side usage not returned by the API.
      </p>
    </div>
  );
}
