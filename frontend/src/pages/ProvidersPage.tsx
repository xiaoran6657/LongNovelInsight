import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  testProvider,
  listProviderPresets,
} from "../api/providers";
import type {
  ModelProvider,
  ModelProviderCreate,
  ModelProviderUpdate,
  ProviderModelPreset,
} from "../api/types";
import { formatDateTime } from "../utils/format";
import LoadingBlock from "../components/LoadingBlock";
import ErrorBlock from "../components/ErrorBlock";
import EmptyState from "../components/EmptyState";

export default function ProvidersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ModelProviderCreate>({
    name: "",
    provider_type: "openai_compatible",
    base_url: "",
    api_key: "",
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState("");
  const [testTargetId, setTestTargetId] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [setDefaultTargetId, setSetDefaultTargetId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Preset state
  const [selectedPresetKey, setSelectedPresetKey] = useState("");
  const [selectedModel, setSelectedModel] = useState<ProviderModelPreset | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });

  const { data: presetData } = useQuery({
    queryKey: ["provider-presets"],
    queryFn: listProviderPresets,
  });

  const presets = presetData?.presets ?? [];
  const activePreset = presets.find((p) => p.provider_key === selectedPresetKey) ?? null;
  const activeModels = activePreset?.models ?? [];
  const activeBaseUrls = activePreset?.base_urls ?? [];

  // Mutations (same as before)
  const createMut = useMutation({
    mutationFn: createProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      resetForm();
    },
    onError: (err: Error) => {
      setFormErrors((prev) => ({ ...prev, _form: err.message }));
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: ModelProviderUpdate }) =>
      updateProvider(id, d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      resetForm();
    },
    onError: (err: Error) => {
      setFormErrors((prev) => ({ ...prev, _form: err.message }));
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      setDeleteTargetId(null);
      setActionError("");
    },
    onError: (err: Error) => {
      setActionError(`Delete failed: ${err.message}`);
      setDeleteTargetId(null);
    },
  });

  const testMut = useMutation({
    mutationFn: testProvider,
  });

  function resetForm() {
    setShowForm(false);
    setEditId(null);
    setForm({ name: "", provider_type: "openai_compatible", base_url: "", api_key: "" });
    setFormErrors({});
    setSelectedPresetKey("");
    setSelectedModel(null);
    setShowAdvanced(false);
  }

  function handleSelectPreset(key: string) {
    setSelectedPresetKey(key);
    const preset = presets.find((p) => p.provider_key === key);
    if (!preset) return;
    // Auto-select first base_url
    const bu = preset.base_urls[0]?.base_url ?? "";
    setForm((f) => ({ ...f, base_url: bu, model_name: "" }));
    setSelectedModel(null);
    // Detect preset on base_url change
    if (!editId) {
      setFormErrors({});
    }
  }

  function handleSelectModel(mn: string) {
    const model = activeModels.find((m) => m.model_name === mn) ?? null;
    setSelectedModel(model);
    setForm((f) => ({
      ...f,
      model_name: mn,
      context_window: model?.context_window ?? f.context_window,
      max_output_tokens: model?.recommended_max_output_tokens ?? f.max_output_tokens,
      temperature: model?.default_temperature ?? f.temperature,
    }));
  }

  function handleSelectBaseUrl(url: string) {
    setForm((f) => ({ ...f, base_url: url }));
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Required";
    if (!form.base_url.trim()) errors.base_url = "Required";
    if (!editId && !form.api_key?.trim()) errors.api_key = "Required";
    const cw = form.context_window ?? 0;
    if (cw !== 0 && cw <= 0) errors.context_window = "Must be > 0";
    const mot = form.max_output_tokens ?? 0;
    if (mot !== 0 && mot <= 0) errors.max_output_tokens = "Must be > 0";
    const temp = form.temperature ?? 0;
    if (temp !== 0 && (temp < 0 || temp > 2)) errors.temperature = "Must be 0–2";
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    const data: ModelProviderCreate = {
      ...form,
      model_name: form.model_name || "",
    };
    if (editId) {
      const upd: ModelProviderUpdate = { ...data };
      if (!upd.api_key?.trim()) delete upd.api_key;
      updateMut.mutate({ id: editId, data: upd });
    } else {
      createMut.mutate(data);
    }
  }

  function startCreate() {
    setEditId(null);
    setForm({ name: "", provider_type: "openai_compatible", base_url: "", api_key: "" });
    setSelectedPresetKey("");
    setSelectedModel(null);
    setShowAdvanced(false);
    setShowForm(true);
    setFormErrors({});
  }

  function startEdit(p: ModelProvider) {
    setEditId(p.id);
    setForm({
      name: p.name,
      provider_type: p.provider_type,
      base_url: p.base_url,
      api_key: "",
      model_name: p.model_name || "",
      context_window: p.context_window || undefined,
      max_output_tokens: p.max_output_tokens || undefined,
      temperature: p.temperature || undefined,
      is_default: p.is_default,
    });
    // Try to detect preset from base_url
    const preset = presets.find(
      (pr) => pr.base_urls.some((bu) => bu.base_url === p.base_url)
    );
    setSelectedPresetKey(preset?.provider_key ?? "");
    setSelectedModel(null);
    setShowForm(true);
    setFormErrors({});
  }

  function handleSetDefault(id: string) {
    setSetDefaultTargetId(id);
    updateMut.mutate({ id, data: { is_default: true } });
  }

  function handleDelete(id: string) {
    setActionError("");
    if (window.confirm("Delete this provider? This cannot be undone.")) {
      setDeleteTargetId(id);
      deleteMut.mutate(id);
    }
  }

  function handleTest(id: string, modelName: string) {
    setActionError("");
    if (!modelName) {
      setActionError("Select a model before testing.");
      return;
    }
    if (
      !window.confirm(
        "This will call the provider API and may consume credits. Continue?"
      )
    )
      return;
    setTestTargetId(id);
    testMut.mutate(id);
  }

  const isSaving = createMut.isPending || updateMut.isPending;
  const providers = data?.providers ?? [];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <h2 style={{ marginBottom: 0 }}>Providers</h2>
        {!showForm && <button onClick={startCreate}>New Provider</button>}
      </div>

      <p className="text-dim" style={{ marginBottom: "1rem" }}>
        API keys are stored in your local backend database. The frontend never
        saves or displays plaintext keys.
      </p>

      {actionError && (
        <div
          className="card card-error"
          style={{
            padding: "0.5rem 0.75rem",
            borderRadius: 4,
            fontSize: "0.9rem",
            marginBottom: "0.75rem",
          }}
        >
          {actionError}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="card">
          <h3>{editId ? "Edit Provider" : "New Provider"}</h3>

          {formErrors._form && (
            <div
              className="card-error"
              style={{
                padding: "0.5rem 0.75rem",
                marginBottom: "0.75rem",
                borderRadius: 4,
                fontSize: "0.9rem",
              }}
            >
              {formErrors._form}
            </div>
          )}

          <div className="provider-form-grid">
            {/* Name */}
            <label>
              Name <span style={{ color: "#e74c3c" }}>*</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My DeepSeek"
              />
              {formErrors.name && (
                <span className="field-error">{formErrors.name}</span>
              )}
            </label>

            {/* Preset selector */}
            <label>
              Provider Preset
              <select
                value={selectedPresetKey}
                onChange={(e) => handleSelectPreset(e.target.value)}
              >
                <option value="">Custom OpenAI-compatible</option>
                {presets
                  .filter((p) => p.provider_key !== "openai_compatible")
                  .map((p) => (
                    <option key={p.provider_key} value={p.provider_key}>
                      {p.display_name}
                    </option>
                  ))}
              </select>
              <span className="text-dim" style={{ fontSize: "0.72rem" }}>
                Choose a known provider to auto-fill Base URL and models
              </span>
            </label>

            {/* Base URL */}
            <label>
              Base URL <span style={{ color: "#e74c3c" }}>*</span>
              {activeBaseUrls.length > 0 && (
                <select
                  value={form.base_url}
                  onChange={(e) => handleSelectBaseUrl(e.target.value)}
                >
                  {activeBaseUrls.map((bu) => (
                    <option key={bu.base_url} value={bu.base_url}>
                      {bu.label} ({bu.base_url})
                    </option>
                  ))}
                  <option value="">Custom...</option>
                </select>
              )}
              <input
                type="url"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                placeholder="https://api.deepseek.com"
                style={{
                  marginTop: activeBaseUrls.length > 0 ? "0.25rem" : 0,
                }}
              />
              {formErrors.base_url && (
                <span className="field-error">{formErrors.base_url}</span>
              )}
            </label>

            {/* Model Name */}
            <label>
              Model Name
              {activeModels.length > 0 ? (
                <select
                  value={form.model_name ?? ""}
                  onChange={(e) => handleSelectModel(e.target.value)}
                >
                  <option value="">Select a model...</option>
                  {activeModels.map((m) => (
                    <option key={m.model_name} value={m.model_name}>
                      {m.display_name}
                      {m.tags.includes("recommended") ? " (recommended)" : ""}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={form.model_name ?? ""}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  placeholder="e.g. deepseek-chat"
                />
              )}
              {/* Always allow manual override */}
              {activeModels.length > 0 && (
                <input
                  type="text"
                  value={form.model_name ?? ""}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  placeholder="Or type custom model name..."
                  style={{ marginTop: "0.25rem", fontSize: "0.85rem" }}
                />
              )}
              <span className="text-dim" style={{ fontSize: "0.72rem" }}>
                Can be set now or configured per Topic later
              </span>
              {formErrors.model_name && (
                <span className="field-error">{formErrors.model_name}</span>
              )}
            </label>

            {/* API Key */}
            <label>
              API Key{" "}
              {!editId && <span style={{ color: "#e74c3c" }}>*</span>}
              {editId && (
                <span style={{ color: "#888", fontWeight: 400 }}>
                  (leave empty to keep current)
                </span>
              )}
              <input
                type="password"
                value={form.api_key ?? ""}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder="sk-..."
              />
              {formErrors.api_key && (
                <span className="field-error">{formErrors.api_key}</span>
              )}
            </label>
          </div>

          {/* Advanced settings toggle */}
          <p
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              cursor: "pointer",
              color: "#888",
              fontSize: "0.85rem",
              marginTop: "0.75rem",
              marginBottom: 0,
              userSelect: "none",
            }}
          >
            {showAdvanced ? "▾ Advanced" : "▸ Advanced"}
          </p>

          {showAdvanced && (
            <div className="provider-form-grid" style={{ marginTop: "0.5rem" }}>
              <label>
                Context Window
                <input
                  type="number"
                  min={0}
                  value={form.context_window ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      context_window:
                        e.target.value === "" ? undefined : Number(e.target.value),
                    })
                  }
                  placeholder="Leave blank for preset default"
                />
                {formErrors.context_window && (
                  <span className="field-error">{formErrors.context_window}</span>
                )}
              </label>

              <label>
                Max Output Tokens
                <input
                  type="number"
                  min={0}
                  value={form.max_output_tokens ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      max_output_tokens:
                        e.target.value === "" ? undefined : Number(e.target.value),
                    })
                  }
                  placeholder="Leave blank for preset default"
                />
                {formErrors.max_output_tokens && (
                  <span className="field-error">
                    {formErrors.max_output_tokens}
                  </span>
                )}
              </label>

              <label>
                Temperature
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={form.temperature ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      temperature:
                        e.target.value === "" ? undefined : Number(e.target.value),
                    })
                  }
                  placeholder="Leave blank for preset default"
                />
                {formErrors.temperature && (
                  <span className="field-error">{formErrors.temperature}</span>
                )}
              </label>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.is_default ?? false}
                  onChange={(e) =>
                    setForm({ ...form, is_default: e.target.checked })
                  }
                />
                <span>Set as default</span>
              </label>
            </div>
          )}

          <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
            <button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : editId ? "Update" : "Create"}
            </button>
            <button type="button" onClick={resetForm} disabled={isSaving}>
              Cancel
            </button>
            {selectedModel && (
              <span className="text-dim" style={{ fontSize: "0.8rem", alignSelf: "center" }}>
                {selectedModel.display_name}
                {selectedModel.context_window
                  ? ` · ${(selectedModel.context_window / 1000).toFixed(0)}K ctx`
                  : ""}
                {selectedModel.supports_thinking ? " · thinking" : ""}
              </span>
            )}
          </div>
        </form>
      )}

      {isLoading && <LoadingBlock text="Loading providers..." />}

      {isError && (
        <ErrorBlock
          title="Failed to load providers"
          message={error instanceof Error ? error.message : "Unknown error"}
        />
      )}

      {!isLoading && !isError && providers.length === 0 && (
        <EmptyState
          title="No providers configured"
          description="Add one to get started with LLM analysis."
          action={
            showForm
              ? undefined
              : { label: "Add Provider", onClick: startCreate }
          }
        />
      )}

      {providers.map((p) => (
        <div className="card" key={p.id}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div>
              <p>
                <strong>{p.name}</strong>{" "}
                {p.is_default && <span className="badge-default">Default</span>}
              </p>
              <p className="text-dim">
                {p.provider_type} {p.model_name ? `· ${p.model_name}` : "· Model not set"}
              </p>
              <p className="text-dim" style={{ fontSize: "0.85rem" }}>
                {p.base_url}
              </p>
              <p className="text-dim" style={{ fontSize: "0.85rem" }}>
                API Key: <code>{p.masked_api_key}</code>
              </p>
              {p.context_window > 0 && (
                <p className="text-dim" style={{ fontSize: "0.8rem" }}>
                  Context: {p.context_window.toLocaleString()}{" "}
                  {p.max_output_tokens > 0
                    ? `· Max output: ${p.max_output_tokens.toLocaleString()}`
                    : ""}{" "}
                  {p.temperature > 0 ? `· Temp: ${p.temperature}` : ""}
                </p>
              )}
              <p className="text-dim" style={{ fontSize: "0.8rem" }}>
                Created: {formatDateTime(p.created_at)}
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
              <button
                onClick={() => handleTest(p.id, p.model_name)}
                disabled={(testTargetId === p.id && testMut.isPending) || !p.model_name}
                title={!p.model_name ? "Select a model before testing" : ""}
              >
                {testTargetId === p.id && testMut.isPending
                  ? "Testing..."
                  : "Test"}
              </button>
              <button onClick={() => startEdit(p)}>Edit</button>
              {!p.is_default && (
                <button
                  onClick={() => handleSetDefault(p.id)}
                  disabled={
                    setDefaultTargetId === p.id && updateMut.isPending
                  }
                >
                  {setDefaultTargetId === p.id && updateMut.isPending
                    ? "Setting..."
                    : "Set Default"}
                </button>
              )}
              <button
                className="btn-danger"
                onClick={() => handleDelete(p.id)}
                disabled={deleteTargetId === p.id && deleteMut.isPending}
              >
                {deleteTargetId === p.id && deleteMut.isPending
                  ? "Deleting..."
                  : "Delete"}
              </button>
            </div>
          </div>

          {testMut.data && testTargetId === p.id && (
            <div
              className={
                testMut.data.success ? "test-result-ok" : "test-result-fail"
              }
              style={{
                marginTop: "0.75rem",
                padding: "0.5rem 0.75rem",
                borderRadius: 4,
                fontSize: "0.9rem",
              }}
            >
              {testMut.data.success
                ? `Connected — ${testMut.data.latency_ms}ms`
                : `Failed: ${testMut.data.message}`}
            </div>
          )}

          {testMut.isError && testTargetId === p.id && (
            <div
              style={{
                marginTop: "0.75rem",
                padding: "0.5rem 0.75rem",
                borderRadius: 4,
                fontSize: "0.9rem",
                background: "#fff5f5",
                color: "#e74c3c",
              }}
            >
              {testMut.error instanceof Error
                ? testMut.error.message
                : "Test failed"}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
