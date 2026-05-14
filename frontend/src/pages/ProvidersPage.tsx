import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  testProvider,
} from "../api/providers";
import type { ModelProvider, ModelProviderCreate, ModelProviderUpdate } from "../api/types";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString();
}

const EMPTY_FORM: ModelProviderCreate = {
  name: "",
  provider_type: "openai_compatible",
  base_url: "",
  model_name: "",
  api_key: "",
  context_window: 1_000_000,
  max_output_tokens: 8192,
  temperature: 0.2,
  is_default: false,
};

export default function ProvidersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ModelProviderCreate>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });

  const createMut = useMutation({
    mutationFn: createProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      setShowForm(false);
      setEditId(null);
      setForm(EMPTY_FORM);
      setFormErrors({});
    },
    onError: (err: Error) => {
      setFormErrors((prev) => ({ ...prev, _form: err.message }));
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ModelProviderUpdate }) =>
      updateProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      setShowForm(false);
      setEditId(null);
      setForm(EMPTY_FORM);
      setFormErrors({});
    },
    onError: (err: Error) => {
      setFormErrors((prev) => ({ ...prev, _form: err.message }));
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });

  const testMut = useMutation({
    mutationFn: testProvider,
  });

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Required";
    if (!form.base_url.trim()) errors.base_url = "Required";
    if (!form.model_name.trim()) errors.model_name = "Required";
    if (!editId && !form.api_key.trim()) errors.api_key = "Required";
    const temp = form.temperature ?? 0;
    if (temp < 0 || temp > 2) errors.temperature = "Must be 0–2";
    if ((form.context_window ?? 0) <= 0)
      errors.context_window = "Must be > 0";
    if ((form.max_output_tokens ?? 0) <= 0)
      errors.max_output_tokens = "Must be > 0";
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    if (editId) {
      const updateData: ModelProviderUpdate = { ...form };
      if (!updateData.api_key?.trim()) delete updateData.api_key;
      updateMut.mutate({ id: editId, data: updateData });
    } else {
      createMut.mutate(form);
    }
  }

  function startCreate() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setFormErrors({});
  }

  function startEdit(p: ModelProvider) {
    setEditId(p.id);
    setForm({
      name: p.name,
      provider_type: p.provider_type,
      base_url: p.base_url,
      model_name: p.model_name,
      api_key: "",
      context_window: p.context_window,
      max_output_tokens: p.max_output_tokens,
      temperature: p.temperature,
      is_default: p.is_default,
    });
    setShowForm(true);
    setFormErrors({});
  }

  function cancelForm() {
    setShowForm(false);
    setEditId(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
  }

  function handleSetDefault(id: string) {
    updateMut.mutate({ id, data: { is_default: true } });
  }

  function handleDelete(id: string) {
    if (window.confirm("Delete this provider?")) {
      deleteMut.mutate(id);
    }
  }

  function handleTest(id: string) {
    testMut.mutate(id);
  }

  function fieldError(name: string): string | undefined {
    return formErrors[name];
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

      {showForm && (
        <form onSubmit={handleSubmit} className="card">
          <h3>{editId ? "Edit Provider" : "New Provider"}</h3>

          {formErrors._form && (
            <div className="card-error" style={{ padding: "0.5rem 0.75rem", marginBottom: "0.75rem", borderRadius: 4, fontSize: "0.9rem" }}>
              {formErrors._form}
            </div>
          )}

          <div className="provider-form-grid">
            <label>
              Name <span style={{ color: "#e74c3c" }}>*</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => {
                  setForm({ ...form, name: e.target.value });
                  if (fieldError("name")) setFormErrors((prev) => { const n = { ...prev }; delete n.name; return n; });
                }}
              />
              {fieldError("name") && <span className="field-error">{fieldError("name")}</span>}
            </label>

            <label>
              Provider Type
              <input type="text" value="openai_compatible" disabled />
            </label>

            <label>
              Base URL <span style={{ color: "#e74c3c" }}>*</span>
              <input
                type="url"
                value={form.base_url}
                onChange={(e) => {
                  setForm({ ...form, base_url: e.target.value });
                  if (fieldError("base_url")) setFormErrors((prev) => { const n = { ...prev }; delete n.base_url; return n; });
                }}
                placeholder="https://api.deepseek.com"
              />
              {fieldError("base_url") && <span className="field-error">{fieldError("base_url")}</span>}
            </label>

            <label>
              Model Name <span style={{ color: "#e74c3c" }}>*</span>
              <input
                type="text"
                value={form.model_name}
                onChange={(e) => {
                  setForm({ ...form, model_name: e.target.value });
                  if (fieldError("model_name")) setFormErrors((prev) => { const n = { ...prev }; delete n.model_name; return n; });
                }}
                placeholder="deepseek-chat"
              />
              {fieldError("model_name") && <span className="field-error">{fieldError("model_name")}</span>}
            </label>

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
                value={form.api_key}
                onChange={(e) => {
                  setForm({ ...form, api_key: e.target.value });
                  if (fieldError("api_key")) setFormErrors((prev) => { const n = { ...prev }; delete n.api_key; return n; });
                }}
                placeholder="sk-..."
              />
              {fieldError("api_key") && <span className="field-error">{fieldError("api_key")}</span>}
            </label>

            <label>
              Context Window
              <input
                type="number"
                min={1}
                value={form.context_window}
                onChange={(e) => {
                  setForm({ ...form, context_window: Number(e.target.value) });
                }}
              />
              {fieldError("context_window") && <span className="field-error">{fieldError("context_window")}</span>}
            </label>

            <label>
              Max Output Tokens
              <input
                type="number"
                min={1}
                value={form.max_output_tokens}
                onChange={(e) => {
                  setForm({ ...form, max_output_tokens: Number(e.target.value) });
                }}
              />
              {fieldError("max_output_tokens") && <span className="field-error">{fieldError("max_output_tokens")}</span>}
            </label>

            <label>
              Temperature (0–2)
              <input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature}
                onChange={(e) => {
                  setForm({ ...form, temperature: Number(e.target.value) });
                }}
              />
              {fieldError("temperature") && <span className="field-error">{fieldError("temperature")}</span>}
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) =>
                  setForm({ ...form, is_default: e.target.checked })
                }
              />
              <span>Set as default</span>
            </label>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
            <button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : editId ? "Update" : "Create"}
            </button>
            <button type="button" onClick={cancelForm} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {isLoading && (
        <div className="card">
          <p className="text-dim">Loading providers...</p>
        </div>
      )}

      {isError && (
        <div className="card card-error">
          <p>
            <strong>Failed to load providers.</strong>
          </p>
          <p className="text-dim">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      )}

      {!isLoading && !isError && providers.length === 0 && (
        <div className="card">
          <p className="text-dim">
            No providers configured yet. Add one to get started.
          </p>
        </div>
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
                {p.is_default && (
                  <span className="badge-default">Default</span>
                )}
              </p>
              <p className="text-dim">
                {p.provider_type} &middot; {p.model_name}
              </p>
              <p className="text-dim" style={{ fontSize: "0.85rem" }}>
                {p.base_url}
              </p>
              <p className="text-dim" style={{ fontSize: "0.85rem" }}>
                API Key: <code>{p.masked_api_key}</code>
              </p>
              <p className="text-dim" style={{ fontSize: "0.8rem" }}>
                Context: {p.context_window.toLocaleString()} &middot;{" "}
                Max output: {p.max_output_tokens.toLocaleString()} &middot;{" "}
                Temp: {p.temperature}
              </p>
              <p className="text-dim" style={{ fontSize: "0.8rem" }}>
                Created: {formatDate(p.created_at)}
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
              <button onClick={() => handleTest(p.id)} disabled={testMut.isPending}>
                {testMut.isPending && testMut.variables === p.id
                  ? "Testing..."
                  : "Test"}
              </button>
              <button onClick={() => startEdit(p)}>Edit</button>
              {!p.is_default && (
                <button onClick={() => handleSetDefault(p.id)}>
                  Set Default
                </button>
              )}
              <button
                className="btn-danger"
                onClick={() => handleDelete(p.id)}
              >
                Delete
              </button>
            </div>
          </div>

          {testMut.data && testMut.variables === p.id && (
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

          {testMut.isError && testMut.variables === p.id && (
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
