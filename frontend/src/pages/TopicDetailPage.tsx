import { useState, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTopic, bindProvider } from "../api/topics";
import { listProviders } from "../api/providers";
import {
  uploadDocument,
  getCurrentDocument,
  deleteCurrentDocument,
} from "../api/documents";
import {
  parseTopic,
  listChapters,
  listChunks,
  getStorage,
} from "../api/parse";

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Provider binding state
  const [bindProviderId, setBindProviderId] = useState("");
  const [bindError, setBindError] = useState("");

  // Document state
  const [uploadError, setUploadError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Chunks state
  const [showChunkText, setShowChunkText] = useState(false);

  // Parse state
  const [parseError, setParseError] = useState("");

  // Queries
  const {
    data: topic,
    isLoading: topicLoading,
    isError: topicError,
    error: topicErr,
  } = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => getTopic(topicId!),
    enabled: !!topicId,
  });

  const { data: providerData } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });

  const {
    data: doc,
    isLoading: docLoading,
    isError: docError,
  } = useQuery({
    queryKey: ["document", topicId],
    queryFn: () => getCurrentDocument(topicId!),
    enabled: !!topicId,
    retry: false,
  });

  const hasDoc = !!doc && !docError && !("detail" in doc);

  const { data: chapterData } = useQuery({
    queryKey: ["chapters", topicId],
    queryFn: () => listChapters(topicId!),
    enabled: !!topicId && !!hasDoc,
  });

  const { data: chunkData } = useQuery({
    queryKey: ["chunks", topicId, showChunkText],
    queryFn: () =>
      listChunks(topicId!, {
        include_text: showChunkText,
        limit: 20,
      }),
    enabled: !!topicId && !!hasDoc,
  });

  const { data: storageData } = useQuery({
    queryKey: ["storage", topicId],
    queryFn: () => getStorage(topicId!),
    enabled: !!topicId && !!hasDoc,
  });

  // Mutations
  const bindMut = useMutation({
    mutationFn: (providerId: string) => bindProvider(topicId!, providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setBindError("");
      setBindProviderId("");
    },
    onError: (err: Error) => setBindError(err.message),
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadDocument(topicId!, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["document", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setUploadError("");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err: Error) => setUploadError(err.message),
  });

  const deleteDocMut = useMutation({
    mutationFn: () => deleteCurrentDocument(topicId!),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["document", topicId] });
      queryClient.removeQueries({ queryKey: ["chapters", topicId] });
      queryClient.removeQueries({ queryKey: ["chunks", topicId] });
      queryClient.removeQueries({ queryKey: ["storage", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      parseMut.reset();
      uploadMut.reset();
      setParseError("");
      setUploadError("");
      setShowChunkText(false);
    },
  });

  const parseMut = useMutation({
    mutationFn: () => parseTopic(topicId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chapters", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chunks", topicId] });
      queryClient.invalidateQueries({ queryKey: ["storage", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setParseError("");
    },
    onError: (err: Error) => setParseError(err.message),
  });

  function handleBind() {
    if (!bindProviderId) {
      setBindError("Select a provider");
      return;
    }
    bindMut.mutate(bindProviderId);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith(".txt")) {
        setUploadError("Only .txt files are accepted");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setUploadError("");
    }
  }

  function handleUpload() {
    if (!selectedFile) {
      setUploadError("Select a .txt file");
      return;
    }
    uploadMut.mutate(selectedFile);
  }

  function handleDeleteDoc() {
    if (window.confirm("Delete this document? All chapters, chunks, and analyses will be removed.")) {
      deleteDocMut.mutate();
    }
  }

  function handleParse() {
    setParseError("");
    parseMut.mutate();
  }

  if (topicLoading) {
    return (
      <div className="card">
        <p className="text-dim">Loading topic...</p>
      </div>
    );
  }

  if (topicError || !topic) {
    return (
      <div>
        <Link to="/topics">&larr; Back to Topics</Link>
        <div className="card card-error" style={{ marginTop: "1rem" }}>
          <p>
            <strong>
              {topicErr instanceof Error ? topicErr.message : "Topic not found"}
            </strong>
          </p>
        </div>
      </div>
    );
  }

  const providers = providerData?.providers ?? [];
  const boundProvider = providers.find((p) => p.id === topic.provider_id);
  const chapters = chapterData?.chapters ?? [];
  const chunks = chunkData?.chunks ?? [];
  const topicStorage = storageData?.topics?.[0];

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

      {/* Document */}
      <div className="card">
        <h3>Document</h3>

        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", alignItems: "center" }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt"
            onChange={handleFileChange}
          />
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploadMut.isPending}
          >
            {uploadMut.isPending ? "Uploading..." : "Upload"}
          </button>
          {hasDoc && (
            <button
              className="btn-danger"
              onClick={handleDeleteDoc}
              disabled={deleteDocMut.isPending}
            >
              {deleteDocMut.isPending ? "Deleting..." : "Delete Document"}
            </button>
          )}
        </div>

        {uploadError && (
          <div
            className="card-error"
            style={{
              padding: "0.5rem 0.75rem",
              marginBottom: "0.5rem",
              borderRadius: 4,
              fontSize: "0.9rem",
            }}
          >
            {uploadError}
          </div>
        )}

        {hasDoc && (
          <div
            style={{
              background: "#f9f9f9",
              padding: "0.75rem",
              borderRadius: 4,
              fontSize: "0.88rem",
            }}
          >
            <p>
              <strong>File:</strong> {doc.original_filename}
            </p>
            <p>
              <strong>Encoding:</strong> {doc.encoding} ·{" "}
              <strong>Size:</strong> {formatBytes(doc.file_size_bytes)} ·{" "}
              <strong>Chars:</strong> {doc.char_count.toLocaleString()}
            </p>
            <p>
              <strong>Status:</strong>{" "}
              <span className={`status-badge status-${doc.status}`}>
                {doc.status}
              </span>
            </p>
          </div>
        )}

        {!hasDoc && !docLoading && (
          <p className="text-dim">No document uploaded. Select a .txt file and click Upload.</p>
        )}

        {docLoading && <p className="text-dim">Checking document...</p>}
      </div>

      {/* Parse */}
      <div className="card">
        <h3>Parse</h3>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", alignItems: "center" }}>
          <button onClick={handleParse} disabled={!hasDoc || parseMut.isPending}>
            {parseMut.isPending ? "Parsing..." : "Parse Document"}
          </button>
          {!hasDoc && (
            <span className="text-dim" style={{ fontSize: "0.85rem" }}>
              Upload a document first.
            </span>
          )}
        </div>

        {parseError && (
          <div
            className="card-error"
            style={{
              padding: "0.5rem 0.75rem",
              marginBottom: "0.5rem",
              borderRadius: 4,
              fontSize: "0.9rem",
            }}
          >
            {parseError}
          </div>
        )}

        {parseMut.isSuccess && (
          <div
            style={{
              background: "#f0fff5",
              padding: "0.75rem",
              borderRadius: 4,
              fontSize: "0.88rem",
            }}
          >
            <p className="status-ok">Parse complete</p>
            <p>
              <strong>Chapters:</strong> {parseMut.data.chapter_count} ·{" "}
              <strong>Chunks:</strong> {parseMut.data.chunk_count} ·{" "}
              <strong>Estimated tokens:</strong>{" "}
              {parseMut.data.estimated_tokens.toLocaleString()}
            </p>
          </div>
        )}

        {parseMut.isError && !parseError && (
          <div
            className="card-error"
            style={{
              padding: "0.5rem 0.75rem",
              marginBottom: "0.5rem",
              borderRadius: 4,
              fontSize: "0.9rem",
            }}
          >
            {parseMut.error instanceof Error
              ? parseMut.error.message
              : "Parse failed"}
          </div>
        )}
      </div>

      {/* Chapters */}
      {chapters.length > 0 && (
        <div className="card">
          <h3>
            Chapters{" "}
            <span className="text-dim" style={{ fontWeight: 400 }}>
              ({chapters.length})
            </span>
          </h3>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Title</th>
                  <th>Chars</th>
                </tr>
              </thead>
              <tbody>
                {chapters.map((ch) => (
                  <tr key={ch.id}>
                    <td>{ch.chapter_index}</td>
                    <td>{ch.title || <span className="text-dim">—</span>}</td>
                    <td>{ch.char_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Chunks */}
      {chunks.length > 0 && (
        <div className="card">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.5rem",
            }}
          >
            <h3 style={{ marginBottom: 0 }}>
              Chunks Preview{" "}
              <span className="text-dim" style={{ fontWeight: 400 }}>
                (first {Math.min(chunks.length, 20)})
              </span>
            </h3>
            <button onClick={() => setShowChunkText(!showChunkText)}>
              {showChunkText ? "Hide Text" : "Show Text"}
            </button>
          </div>

          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ch</th>
                  <th>Ck</th>
                  <th>Chars</th>
                  <th>Tokens</th>
                  {showChunkText && <th>Text</th>}
                </tr>
              </thead>
              <tbody>
                {chunks.map((ck) => (
                  <tr key={ck.id}>
                    <td>{ck.chapter_index}</td>
                    <td>{ck.chunk_index}</td>
                    <td>{ck.char_count.toLocaleString()}</td>
                    <td>{ck.estimated_tokens}</td>
                    {showChunkText && (
                      <td className="chunk-text">
                        {ck.text
                          ? ck.text.length > 200
                            ? ck.text.slice(0, 200) + "..."
                            : ck.text
                          : ck.text}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Storage */}
      {topicStorage && (
        <div className="card">
          <h3>Storage</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <p>
              <strong>Novel:</strong> {formatBytes(topicStorage.novel_size_bytes)}
            </p>
            <p>
              <strong>Chunks:</strong> {formatBytes(topicStorage.chunks_size_bytes)}
            </p>
            <p>
              <strong>Analyses:</strong>{" "}
              {formatBytes(topicStorage.analyses_size_bytes)}
            </p>
            <p>
              <strong>Total:</strong> {formatBytes(topicStorage.total_bytes)}
            </p>
            <p>
              <strong>Database:</strong>{" "}
              {formatBytes(storageData!.database_size_bytes)}
            </p>
            <p>
              <strong>Data dir:</strong>{" "}
              {formatBytes(storageData!.data_dir_size_bytes)}
            </p>
          </div>
        </div>
      )}

      {/* Analysis */}
      <div className="card">
        <h3>Analysis</h3>
        {topic.analysis_summary &&
        Object.keys(topic.analysis_summary).length > 0 ? (
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

      {/* Chat */}
      <div className="card">
        <h3>Chat</h3>
        <p>
          <Link to={`/topics/${topic.id}/chat`}>Open chat &rarr;</Link>
        </p>
      </div>
    </div>
  );
}
