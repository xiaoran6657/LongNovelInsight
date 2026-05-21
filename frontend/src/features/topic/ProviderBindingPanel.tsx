import type { ModelProvider, EffectiveProviderConfig, ProviderModelPreset } from "../../api/types";
import ProviderConfigForm from "../provider/ProviderConfigForm";

interface Props {
  providers: ModelProvider[];
  effectiveConfig: EffectiveProviderConfig | undefined;
  activePresetModels: ProviderModelPreset[];
  boundProvider: ModelProvider | undefined;
  bindProviderId: string;
  bindError: string;
  bindPending: boolean;
  onBindProviderIdChange: (id: string) => void;
  onBind: () => void;
  editModel: string;
  editMaxTokens: string;
  editTemp: string;
  editThinking: string;
  editParallel: string;
  configDirty: boolean;
  configSaveError: string;
  configErrors: Record<string, string>;
  savePending: boolean;
  onEditModel: (v: string) => void;
  onEditMaxTokens: (v: string) => void;
  onEditTemp: (v: string) => void;
  onEditThinking: (v: string) => void;
  onEditParallel: (v: string) => void;
  onSaveConfig: () => void;
  onApplyPreset: (model: string, maxTok: number, temp: number, thinking: string, parallel: number) => void;
}

export default function ProviderBindingPanel(props: Props) {
  const p = props;

  return (
    <div className="card">
      <h3>Provider</h3>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", alignItems: "flex-start" }}>
        <select value={p.bindProviderId} onChange={(e) => { p.onBindProviderIdChange(e.target.value); }}>
          <option value="">Select provider...</option>
          {p.providers.map((pr) => (
            <option key={pr.id} value={pr.id}>{pr.name}</option>
          ))}
        </select>
        <button onClick={p.onBind} disabled={p.bindPending}>
          {p.bindPending ? "Binding..." : p.boundProvider ? "Change Provider" : "Bind Provider"}
        </button>
        {p.bindError && <span className="field-error">{p.bindError}</span>}
      </div>

      {p.effectiveConfig && p.boundProvider && (
        <div style={{ background: "#f9f9f9", borderRadius: 4, padding: "0.6rem 0.75rem", fontSize: "0.83rem", marginBottom: "0.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
            <p style={{ fontWeight: 600 }}>
              Topic Config{" "}
              <span style={{ color: p.effectiveConfig.is_ready ? "#27ae60" : "#e74c3c", fontSize: "0.78rem", fontWeight: 400 }}>
                {p.effectiveConfig.is_ready ? "ready" : "incomplete"}
                {p.effectiveConfig.missing_fields.length > 0 && ` (missing: ${p.effectiveConfig.missing_fields.join(", ")})`}
              </span>
            </p>
            {p.configDirty && (
              <button onClick={p.onSaveConfig} disabled={p.savePending} style={{ fontSize: "0.78rem", padding: "0.2em 0.5em" }}>
                {p.savePending ? "Saving..." : "Save"}
              </button>
            )}
          </div>
          {p.configSaveError && <p style={{ color: "#e74c3c", fontSize: "0.76rem", marginBottom: "0.3rem" }}>{p.configSaveError}</p>}
          <ProviderConfigForm
            model={p.editModel} maxTokens={p.editMaxTokens}
            temperature={p.editTemp} thinking={p.editThinking}
            parallelism={p.editParallel}
            effectiveConfig={p.effectiveConfig}
            presetModels={p.activePresetModels}
            showParallelism
            onModelChange={p.onEditModel}
            onMaxTokensChange={p.onEditMaxTokens}
            onTempChange={p.onEditTemp}
            onThinkingChange={p.onEditThinking}
            onParallelismChange={p.onEditParallel}
            onPresetSelect={(preset) => p.onApplyPreset(
              preset.model_name,
              preset.recommended_max_output_tokens ?? 2048,
              preset.default_temperature ?? 0.1,
              preset.default_thinking_mode ?? "disabled",
              p.effectiveConfig?.analysis_parallelism ?? 3,
            )}
          />
        </div>
      )}
    </div>
  );
}
