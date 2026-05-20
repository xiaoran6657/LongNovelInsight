import type { ModelProvider, EffectiveProviderConfig, ProviderModelPreset } from "../../api/types";
import TokenRangeSlider from "../../components/TokenRangeSlider";

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
          <div className="topic-config-grid">
            <label>
              {p.configErrors.model && <span style={{ color: "#e74c3c", fontWeight: 700 }}>✗ </span>}
              Model
              {p.activePresetModels.length > 0 ? (
                <select
                  value={p.activePresetModels.some((m) => m.model_name === p.editModel) ? p.editModel : p.editModel ? "__other__" : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "__other__" || !v) { p.onEditModel(""); return; }
                    p.onEditModel(v);
                    const m = p.activePresetModels.find((pm) => pm.model_name === v);
                    if (m) p.onApplyPreset(v, m.recommended_max_output_tokens ?? 2048, m.default_temperature ?? 0.1, m.default_thinking_mode ?? "disabled", p.effectiveConfig?.analysis_parallelism ?? 3);
                  }}
                >
                  <option value="">-- preset --</option>
                  {p.activePresetModels.map((pm) => (
                    <option key={pm.model_name} value={pm.model_name}>{pm.display_name}</option>
                  ))}
                  <option value="__other__">Custom...</option>
                </select>
              ) : null}
              <input type="text" value={p.editModel} onChange={(e) => p.onEditModel(e.target.value)} placeholder="deepseek-chat" />
            </label>
            <label>
              {p.configErrors.maxTokens && <span style={{ color: "#e74c3c", fontWeight: 700 }}>✗ </span>}
              Max Tokens
              <TokenRangeSlider
                value={Number(p.editMaxTokens) || 2048}
                min={512}
                max={16384}
                recommendedValue={p.effectiveConfig?.max_output_tokens ?? undefined}
                onChange={(v) => p.onEditMaxTokens(String(v))}
              />
            </label>
            <label>
              Temperature
              <input type="text" value={p.editTemp} onChange={(e) => p.onEditTemp(e.target.value)} />
            </label>
            <label>
              Thinking
              <select value={p.editThinking} onChange={(e) => p.onEditThinking(e.target.value)}>
                <option value="disabled">Disabled</option>
                <option value="enabled">Enabled</option>
              </select>
            </label>
            <label>
              Parallelism
              <input type="text" value={p.editParallel} onChange={(e) => p.onEditParallel(e.target.value)} />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
