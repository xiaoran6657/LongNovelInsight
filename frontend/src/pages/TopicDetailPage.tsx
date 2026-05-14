import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTopic, bindProvider } from "../api/topics";
import { listProviders } from "../api/providers";

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

export default function TopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const queryClient = useQueryClient();
  const [bindProviderId, setBindProviderId] = useState("");
  const [bindError, setBindError] = useState("");

  const {
    data: topic,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => getTopic(topicId!),
    enabled: !!topicId,
  });

  const { data: providerData } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });

  const bindMut = useMutation({
    mutationFn: (providerId: string) => bindProvider(topicId!, providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setBindError("");
      setBindProviderId("");
    },
    onError: (err: Error) => {
      setBindError(err.message);
    },
  });

  function handleBind() {
    if (!bindProviderId) {
      setBindError("Select a provider");
      return;
    }
    bindMut.mutate(bindProviderId);
  }

  if (isLoading) {
    return (
      <div className="card">
        <p className="text-dim">Loading topic...</p>
      </div>
    );
  }

  if (isError || !topic) {
    return (
      <div>
        <Link to="/topics">&larr; Back to Topics</Link>
        <div className="card card-error" style={{ marginTop: "1rem" }}>
          <p>
            <strong>
              {error instanceof Error ? error.message : "Topic not found"}
            </strong>
          </p>
        </div>
      </div>
    );
  }

  const providers = providerData?.providers ?? [];
  const boundProvider = providers.find((p) => p.id === topic.provider_id);

  return (
    <div>
      <p style={{ marginBottom: "1rem" }}>
        <Link to="/topics">&larr; Back to Topics</Link>
        {" | "}
        <Link to={`/topics/${topic.id}/chat`}>Chat &rarr;</Link>
      </p>

      <h2>{topic.name}</h2>

      {/* Basic Info */}
      <div className="card">
        <h3>Info</h3>
        <p>
          <strong>Status:</strong>{" "}
          <span className={`status-badge status-${topic.status}`}>
            {topic.status}
          </span>
        </p>
        {topic.description && (
          <p>
            <strong>Description:</strong> {topic.description}
          </p>
        )}
        <p>
          <strong>Storage:</strong> {formatBytes(topic.disk_usage_bytes ?? 0)}
        </p>
        <p className="text-dim" style={{ fontSize: "0.85rem" }}>
          Created: {formatDate(topic.created_at)}
          {" · "}
          Updated: {formatDate(topic.updated_at)}
        </p>
      </div>

      {/* Provider */}
      <div className="card">
        <h3>Provider</h3>
        {boundProvider ? (
          <div>
            <p>
              <strong>Bound:</strong> {boundProvider.name} (
              {boundProvider.model_name})
            </p>
            <p className="text-dim" style={{ fontSize: "0.85rem" }}>
              {boundProvider.base_url} · API Key:{" "}
              <code>{boundProvider.masked_api_key}</code>
            </p>
          </div>
        ) : (
          <p className="text-dim">No provider bound.</p>
        )}

        <div
          style={{
            display: "flex",
            gap: "0.5rem",
            marginTop: "0.75rem",
            alignItems: "flex-start",
          }}
        >
          <select
            value={bindProviderId}
            onChange={(e) => {
              setBindProviderId(e.target.value);
              setBindError("");
            }}
          >
            <option value="">Select provider...</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.model_name}){p.is_default ? " [default]" : ""}
              </option>
            ))}
          </select>
          <button onClick={handleBind} disabled={bindMut.isPending}>
            {bindMut.isPending
              ? "Binding..."
              : boundProvider
                ? "Change Provider"
                : "Bind Provider"}
          </button>
          {bindError && <span className="field-error">{bindError}</span>}
        </div>
      </div>

      {/* Placeholder sections */}
      <div className="card">
        <h3>Document</h3>
        {topic.document ? (
          <p>
            <strong>{topic.document.original_filename}</strong> ·{" "}
            {formatBytes(topic.document.file_size_bytes)} ·{" "}
            {topic.document.char_count.toLocaleString()} chars ·{" "}
            <span className={`status-badge status-${topic.document.status}`}>
              {topic.document.status}
            </span>
          </p>
        ) : (
          <p className="text-dim">
            No document uploaded. (Upload will be available in Task 006.)
          </p>
        )}
      </div>

      <div className="card">
        <h3>Parse</h3>
        <p className="text-dim">
          Parse controls will be implemented in Task 006.
        </p>
      </div>

      <div className="card">
        <h3>Analysis</h3>
        {topic.analysis_summary && Object.keys(topic.analysis_summary).length > 0 ? (
          <p>
            {Object.entries(topic.analysis_summary).map(([type, count]) => (
              <span key={type} style={{ marginRight: "1rem" }}>
                <strong>{type}:</strong> {count ?? 0}
              </span>
            ))}
          </p>
        ) : (
          <p className="text-dim">
            No analysis results. (Analysis will be available in Task 007.)
          </p>
        )}
      </div>

      <div className="card">
        <h3>Chat</h3>
        <p className="text-dim">
          <Link to={`/topics/${topic.id}/chat`}>Open chat &rarr;</Link>
          {" · "}Chat will be available in Task 008.
        </p>
      </div>
    </div>
  );
}
