import type { EffectiveProviderConfig } from "../../api/types";

interface Props {
  config: EffectiveProviderConfig | undefined;
  isLoading?: boolean;
}

export default function EffectiveProviderConfigCard({ config, isLoading }: Props) {
  if (isLoading) return <p className="text-dim" style={{ fontSize: "0.82rem" }}>Loading config...</p>;
  if (!config) return <p className="text-dim" style={{ fontSize: "0.82rem" }}>No provider config available.</p>;

  const ready = config.is_ready;

  return (
    <div className="card" style={{ fontSize: "0.82rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
        <h3 style={{ margin: 0, fontSize: "0.9rem" }}>Effective Config</h3>
        <span style={{
          color: ready ? "#27ae60" : "#e74c3c",
          fontWeight: 600, fontSize: "0.78rem",
        }}>
          {ready ? "Ready" : "Incomplete"}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.25rem" }}>
        <div><strong>Provider:</strong> {config.provider_name || "—"}</div>
        <div><strong>Model:</strong> {config.model_name || "—"}</div>
        <div><strong>Max Tokens:</strong> {config.max_output_tokens ?? "—"}</div>
        <div><strong>Temperature:</strong> {config.temperature ?? "—"}</div>
        <div><strong>Thinking:</strong> {config.thinking_mode}</div>
        <div><strong>Parallelism:</strong> {config.analysis_parallelism}</div>
      </div>

      {!ready && config.missing_fields.length > 0 && (
        <p style={{ color: "#e74c3c", fontSize: "0.78rem", marginTop: "0.35rem" }}>
          Missing: {config.missing_fields.join(", ")}
        </p>
      )}
      {config.warnings.length > 0 && (
        <p style={{ color: "#f57f17", fontSize: "0.75rem", marginTop: "0.2rem" }}>
          {config.warnings.join("; ")}
        </p>
      )}
    </div>
  );
}
