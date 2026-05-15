import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listTopics, createTopic, deleteTopic } from "../api/topics";
import { listProviders } from "../api/providers";
import type { TopicCreate } from "../api/types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

const EMPTY_FORM: TopicCreate = {
  name: "",
  description: "",
  provider_id: "",
};

export default function TopicsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TopicCreate>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");

  const {
    data: topicData,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["topics"],
    queryFn: listTopics,
  });

  const {
    data: providerData,
    isError: providerError,
    error: providerErr,
  } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });

  const createMut = useMutation({
    mutationFn: createTopic,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
      setFormErrors({});
    },
    onError: (err: Error) => {
      setFormErrors({ _form: err.message });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteTopic,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setDeleteTargetId(null);
      setDeleteError("");
    },
    onError: (err: Error) => {
      setDeleteError(`Delete failed: ${err.message}`);
      setDeleteTargetId(null);
    },
  });

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Required";
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    const data: TopicCreate = { name: form.name };
    if (form.description?.trim()) data.description = form.description.trim();
    if (form.provider_id) data.provider_id = form.provider_id;
    createMut.mutate(data);
  }

  function handleDelete(id: string, name: string) {
    setDeleteError("");
    if (window.confirm(`Delete topic "${name}"? This will remove all documents, analyses, and chat data.`)) {
      setDeleteTargetId(id);
      deleteMut.mutate(id);
    }
  }

  function startCreate() {
    setForm(EMPTY_FORM);
    setShowForm(true);
    setFormErrors({});
  }

  const providers = providerData?.providers ?? [];
  const topics = topicData?.topics ?? [];

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
        <h2 style={{ marginBottom: 0 }}>Topics</h2>
        {!showForm && <button onClick={startCreate}>New Topic</button>}
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card">
          <h3>New Topic</h3>

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

          <div className="topic-form-grid">
            <label>
              Name <span style={{ color: "#e74c3c" }}>*</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => {
                  setForm({ ...form, name: e.target.value });
                  if (formErrors.name)
                    setFormErrors((prev) => {
                      const n = { ...prev };
                      delete n.name;
                      return n;
                    });
                }}
              />
              {formErrors.name && (
                <span className="field-error">{formErrors.name}</span>
              )}
            </label>

            <label>
              Description
              <input
                type="text"
                value={form.description ?? ""}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>

            <label>
              Provider
              <select
                value={form.provider_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, provider_id: e.target.value || undefined })
                }
              >
                <option value="">None</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.model_name})
                  </option>
                ))}
              </select>
              {providerError && (
                <span className="field-error">
                  Could not load providers:{" "}
                  {providerErr instanceof Error
                    ? providerErr.message
                    : "Unknown error"}
                </span>
              )}
              {!providerError && providers.length === 0 && (
                <span className="field-error">
                  No providers configured.{" "}
                  <Link to="/providers">Add one first</Link>.
                </span>
              )}
            </label>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
            <button type="submit" disabled={createMut.isPending}>
              {createMut.isPending ? "Creating..." : "Create"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setFormErrors({});
              }}
              disabled={createMut.isPending}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {isLoading && (
        <div className="card">
          <p className="text-dim">Loading topics...</p>
        </div>
      )}

      {isError && (
        <div className="card card-error">
          <p>
            <strong>Failed to load topics.</strong>
          </p>
          <p className="text-dim">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      )}

      {deleteError && (
        <div className="card card-error" style={{ padding: "0.5rem 0.75rem", borderRadius: 4, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
          {deleteError}
        </div>
      )}

      {!isLoading && !isError && topics.length === 0 && (
        <div className="card">
          <p className="text-dim">
            No topics yet. Create one to start analyzing a novel.
          </p>
        </div>
      )}

      {topics.map((t) => (
        <div className="card" key={t.id}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div style={{ flex: 1 }}>
              <p>
                <Link
                  to={`/topics/${t.id}`}
                  style={{ fontSize: "1.1rem", fontWeight: 600 }}
                >
                  {t.name}
                </Link>{" "}
                <span className={`status-badge status-${t.status}`}>
                  {t.status}
                </span>
              </p>
              {t.description && (
                <p className="text-dim" style={{ marginBottom: "0.5rem" }}>
                  {t.description}
                </p>
              )}
              <p className="text-dim" style={{ fontSize: "0.85rem" }}>
                Storage: {formatBytes(t.disk_usage_bytes ?? 0)}
                {t.document && (
                  <>
                    {" "}
                    &middot; Document:{" "}
                    {t.document.original_filename ?? t.document.status}
                  </>
                )}
                {t.provider_id && (
                  <>
                    {" "}
                    &middot; Provider:{" "}
                    {providers.find((p) => p.id === t.provider_id)?.name ??
                      t.provider_id}
                  </>
                )}
                {" "}&middot; Created: {formatDate(t.created_at)}
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
              <button
                className="btn-danger"
                onClick={() => handleDelete(t.id, t.name)}
                disabled={deleteTargetId === t.id && deleteMut.isPending}
              >
                {deleteTargetId === t.id && deleteMut.isPending
                  ? "Deleting..."
                  : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
