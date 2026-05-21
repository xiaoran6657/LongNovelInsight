import type { EffectiveProviderConfig, ProviderModelPreset } from "../../api/types";
import TokenRangeSlider from "../../components/TokenRangeSlider";

interface Props {
  model: string;
  maxTokens: string;
  temperature: string;
  thinking: string;
  parallelism?: string;
  effectiveConfig: EffectiveProviderConfig | undefined;
  presetModels: ProviderModelPreset[];
  showParallelism?: boolean;
  onModelChange: (v: string) => void;
  onMaxTokensChange: (v: string) => void;
  onTempChange: (v: string) => void;
  onThinkingChange: (v: string) => void;
  onParallelismChange?: (v: string) => void;
}

const fieldInputStyle: React.CSSProperties = {
  width: "100%", padding: "0.2em 0.35em", fontSize: "0.78rem",
  border: "1px solid #ccc", borderRadius: 3,
};

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: "0.7rem", color: "#888", marginTop: "0.35rem", marginBottom: "0.1rem" }}>{children}</div>;
}

export default function ProviderConfigForm({
  model, maxTokens, temperature, thinking, parallelism,
  effectiveConfig, presetModels, showParallelism,
  onModelChange, onMaxTokensChange, onTempChange, onThinkingChange, onParallelismChange,
}: Props) {
  const isManualModel = !!model && !presetModels.some((m) => m.model_name === model);

  return (
    <div style={{ fontSize: "0.82rem" }}>
      {/* Model */}
      <FieldLabel>Model</FieldLabel>
      {presetModels.length > 0 ? (
        <>
          <select
            value={
              presetModels.some((m) => m.model_name === model)
                ? model
                : model ? "__other__" : ""
            }
            onChange={(e) => {
              const v = e.target.value;
              if (v === "__other__" || !v) { onModelChange(""); return; }
              onModelChange(v);
            }}
            style={fieldInputStyle}
          >
            <option value="">Inherit ({effectiveConfig?.model_name || "none"})</option>
            {presetModels.map((m) => (
              <option key={m.model_name} value={m.model_name}>{m.display_name}</option>
            ))}
            <option value="__other__">Other (type)...</option>
          </select>
          {isManualModel && (
            <input type="text" value={model}
              onChange={(e) => onModelChange(e.target.value)}
              placeholder="Custom model name..."
              style={{ ...fieldInputStyle, marginTop: "0.2rem" }} />
          )}
        </>
      ) : (
        <input type="text" value={model}
          onChange={(e) => onModelChange(e.target.value)}
          placeholder={effectiveConfig?.model_name || "e.g. deepseek-chat"}
          style={fieldInputStyle} />
      )}

      {/* Max Tokens */}
      <FieldLabel>Max Tokens</FieldLabel>
      <TokenRangeSlider
        value={Number(maxTokens) || (effectiveConfig?.max_output_tokens ?? 2048)}
        min={512} max={16384}
        recommendedValue={effectiveConfig?.max_output_tokens ?? undefined}
        onChange={(v) => onMaxTokensChange(String(v))}
      />

      {/* Temperature */}
      <FieldLabel>Temperature (0–2)</FieldLabel>
      <input type="number" min={0} max={2} step={0.1}
        value={temperature}
        onChange={(e) => onTempChange(e.target.value)}
        placeholder={effectiveConfig?.temperature?.toString() || "0.1"}
        className="no-spinner"
        style={fieldInputStyle} />

      {/* Thinking */}
      <FieldLabel>Thinking</FieldLabel>
      <select value={thinking} onChange={(e) => onThinkingChange(e.target.value)} style={fieldInputStyle}>
        <option value="disabled">disabled</option>
        <option value="enabled">enabled</option>
        <option value="provider_default">provider default</option>
      </select>

      {/* Parallelism */}
      {showParallelism && (
        <>
          <FieldLabel>Parallelism (1–6)</FieldLabel>
          <input type="number" min={1} max={6}
            value={parallelism ?? ""}
            onChange={(e) => onParallelismChange?.(e.target.value)}
            placeholder={effectiveConfig?.analysis_parallelism?.toString() || "3"}
            className="no-spinner"
            style={fieldInputStyle} />
        </>
      )}

      {/* Base URL (read-only) */}
      <FieldLabel>Base URL</FieldLabel>
      <p style={{ fontSize: "0.72rem", color: "#888", marginTop: "0.1rem", wordBreak: "break-all" }}>
        {effectiveConfig?.base_url || "—"}
      </p>
    </div>
  );
}
