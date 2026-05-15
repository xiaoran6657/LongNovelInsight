import { useState, useRef, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisOutput } from "../api/types";
import AnalysisOutputCard from "../components/AnalysisOutputCard";
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
import {
  listAnalysisOutputs,
  runAnalysis,
  deleteAnalysisOutputs,
  getAnalysisStatus,
  runSingleAnalysis,
} from "../api/analysis";

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

function groupLatestOutputs(
  outputs: AnalysisOutput[]
): { latest: AnalysisOutput[]; hiddenCounts: Record<string, number> } {
  const grouped: Record<string, AnalysisOutput[]> = {};
  for (const o of outputs) {
    if (!grouped[o.output_type]) grouped[o.output_type] = [];
    grouped[o.output_type].push(o);
  }
  const latest: AnalysisOutput[] = [];
  const hiddenCounts: Record<string, number> = {};
  for (const [type, items] of Object.entries(grouped)) {
    items.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    latest.push(items[0]);
    if (items.length > 1) hiddenCounts[type] = items.length - 1;
  }
  latest.sort((a, b) => a.output_type.localeCompare(b.output_type));
  return { latest, hiddenCounts };
}

export default function TopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const runAnalysisInFlightRef = useRef(false);

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

  // Analysis state
  const [limitChunks, setLimitChunks] = useState(5);
  const [runError, setRunError] = useState("");
  const [outputTypeFilter, setOutputTypeFilter] = useState("");

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

  const { data: allChunksMeta } = useQuery({
    queryKey: ["chunks-count", topicId],
    queryFn: () =>
      listChunks(topicId!, { include_text: false, limit: 1000 }),
    enabled: !!topicId && !!hasDoc,
  });

  const totalChunkCount = allChunksMeta?.chunks.length ?? 0;

  // Clamp limitChunks to actual total (e.g. short text with < 5 chunks)
  useEffect(() => {
    if (totalChunkCount > 0) {
      setLimitChunks((prev) => Math.min(prev, totalChunkCount));
    }
  }, [totalChunkCount]);

  const { data: storageData } = useQuery({
    queryKey: ["storage", topicId],
    queryFn: () => getStorage(topicId!),
    enabled: !!topicId && !!hasDoc,
  });

  const { data: outputData } = useQuery({
    queryKey: ["outputs", topicId, outputTypeFilter],
    queryFn: () =>
      listAnalysisOutputs(topicId!, outputTypeFilter || undefined),
    enabled: !!topicId,
  });

  const { data: allOutputsData } = useQuery({
    queryKey: ["outputs", topicId],
    queryFn: () => listAnalysisOutputs(topicId!),
    enabled: !!topicId,
  });

  const { data: jobStatus } = useQuery({
    queryKey: ["analysis-status", topicId],
    queryFn: () => getAnalysisStatus(topicId!),
    enabled: !!topicId,
    refetchInterval: 3000,
  });

  const hasActiveJob =
    jobStatus?.latest_job?.status === "pending" ||
    jobStatus?.latest_job?.status === "running";

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
      // Optimistically update topic status so UI updates immediately
      // Optimistically update topic status and chunk count so UI updates immediately
      queryClient.setQueryData(["topic", topicId], (old: unknown) => {
        if (old && typeof old === "object") {
          return { ...(old as Record<string, unknown>), status: "parsed" };
        }
        return old;
      });
      // Also set chunk count from parse result so limit-chunks max updates
      if (parseMut.data) {
        const fakeChunks = Array.from(
          { length: parseMut.data.chunk_count },
          (_, i) => ({ id: `opt-${i}`, char_count: 2000 })
        );
        queryClient.setQueryData(["chunks-count", topicId], {
          chunks: fakeChunks,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chapters", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chunks", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chunks-count", topicId] });
      queryClient.invalidateQueries({ queryKey: ["storage", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setParseError("");
    },
    onError: (err: Error) => setParseError(err.message),
  });

  const runAnalysisMut = useMutation({
    mutationFn: async () => {
      setRunning();
      return runAnalysis(topicId!, limitChunks);
    },
    onSuccess: (data) => {
      clearRunning();
      runAnalysisInFlightRef.current = false;
      queryClient.invalidateQueries({ queryKey: ["outputs", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      queryClient.invalidateQueries({ queryKey: ["analysis-status", topicId] });
      setRunError("");
      // Persist analysis summary with real token usage
      const outputs = data.outputs ?? [];
      const completed = outputs.map((o) => o.output_type);
      const realInput = outputs.reduce((s, o) => s + (o.prompt_tokens ?? 0), 0);
      const realOutput = outputs.reduce(
        (s, o) => s + (o.completion_tokens ?? 0),
        0
      );
      const summary = {
        elapsedSec,
        estimatedInputTokens: realInput,
        estimatedOutputTokens: realOutput,
        completedTypes: completed,
      };
      setRunSummary(summary);
      sessionStorage.setItem(summaryKey, JSON.stringify(summary));
    },
    onError: (err: Error) => {
      clearRunning();
      clearSummary();
      runAnalysisInFlightRef.current = false;
      setRunError(err.message);
    },
  });

  const deleteOutputsMut = useMutation({
    mutationFn: () => deleteAnalysisOutputs(topicId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["outputs", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });

  const [retryingType, setRetryingType] = useState<string | null>(null);

  const retrySingleMut = useMutation({
    mutationFn: ({
      outputType,
      deepen,
    }: {
      outputType: string;
      deepen: boolean;
    }) => runSingleAnalysis(topicId!, outputType, limitChunks, deepen),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["outputs", topicId] });
      setRetryingType(null);
      setRunSummary((prev) => {
        if (!prev) return prev;
        const newCompleted = [...new Set([...prev.completedTypes, data.output.output_type])];
        const updated = {
          ...prev,
          completedTypes: newCompleted,
          estimatedInputTokens:
            prev.estimatedInputTokens + (data.output.prompt_tokens ?? 0),
          estimatedOutputTokens:
            prev.estimatedOutputTokens + (data.output.completion_tokens ?? 0),
        };
        sessionStorage.setItem(summaryKey, JSON.stringify(updated));
        return updated;
      });
    },
    onError: () => {
      setRetryingType(null);
      alert("Retry failed. Check backend logs for details.");
    },
  });

  function handleRetryType(outputType: string, deepen: boolean) {
    setRetryingType(outputType);
    retrySingleMut.mutate({ outputType, deepen });
  }

  const isParsed =
    parseMut.isSuccess ||
    topic?.status === "parsed" ||
    topic?.status === "ready" ||
    (chapterData?.chapters?.length ?? 0) > 0;

  // Persist analysis-running flag across page refreshes via sessionStorage
  const runningKey = `analysis_running_${topicId}`;
  const [recoveredRunning, setRecoveredRunning] = useState(
    () => sessionStorage.getItem(runningKey) === "1"
  );

  // On mount, if sessionStorage says running, poll for outputs until they appear
  useEffect(() => {
    if (!recoveredRunning || !topicId) return;
    const interval = setInterval(async () => {
      try {
        const res = await listAnalysisOutputs(topicId);
        if (res.outputs.length > 0) {
          clearInterval(interval);
          sessionStorage.removeItem(runningKey);
          setRecoveredRunning(false);
          queryClient.invalidateQueries({ queryKey: ["outputs", topicId] });
          queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
        }
      } catch {
        // backend may still be busy — keep polling
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [recoveredRunning, topicId, runningKey, queryClient]);

  const isAnalysisRunning =
    runAnalysisMut.isPending || recoveredRunning;

  const [elapsedSec, setElapsedSec] = useState(0);
  const [retryElapsed, setRetryElapsed] = useState(0);

  type RunSummary = {
    elapsedSec: number;
    estimatedInputTokens: number;
    estimatedOutputTokens: number;
    completedTypes: string[];
  } | null;

  const summaryKey = `analysis_summary_${topicId}`;
  const [runSummary, setRunSummary] = useState<RunSummary>(() => {
    const raw = sessionStorage.getItem(summaryKey);
    if (!raw) return null;
    try { return JSON.parse(raw) as RunSummary; } catch { return null; }
  });

  // Poll unfiltered outputs during analysis for progress tracking
  useEffect(() => {
    if (!isAnalysisRunning || !topicId) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["outputs", topicId] });
    }, 2000);
    return () => clearInterval(interval);
  }, [isAnalysisRunning, topicId, queryClient]);

  // Elapsed time counter during analysis
  useEffect(() => {
    if (!isAnalysisRunning) {
      setElapsedSec(0);
      return;
    }
    setElapsedSec(0);
    const interval = setInterval(() => {
      setElapsedSec((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isAnalysisRunning]);

  // Retry timer — ticks during single-type re-analysis
  useEffect(() => {
    if (!retryingType) {
      setRetryElapsed(0);
      return;
    }
    setRetryElapsed(0);
    const interval = setInterval(() => {
      setRetryElapsed((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [retryingType]);

  const ALL_TYPES = [
    "overview",
    "characters",
    "relations",
    "events",
    "causality",
    "themes",
  ] as const;

  function setRunning() {
    sessionStorage.setItem(runningKey, "1");
    setRecoveredRunning(true);
  }

  function clearRunning() {
    sessionStorage.removeItem(runningKey);
    setRecoveredRunning(false);
  }

  function clearSummary() {
    sessionStorage.removeItem(summaryKey);
    setRunSummary(null);
  }

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

  function handleRunAnalysis() {
    if (runAnalysisInFlightRef.current) return;
    if (hasActiveJob) {
      setRunError("Analysis is already running for this topic");
      return;
    }
    setRunError("");
    const existing = outputData?.outputs ?? [];
    if (existing.length > 0) {
      if (
        !window.confirm(
          `${existing.length} existing output(s) will be replaced. Continue?`
        )
      )
        return;
    }
    // Save token estimate for summary bar
    const selChunks = (allChunksMeta?.chunks ?? []).slice(0, limitChunks);
    const selChars = selChunks.reduce((s, c) => s + c.char_count, 0);
    const chunkToks = Math.round(selChars / 3.5);
    const promptToks = 600 * 6;
    const outToks = 800 * 6;
    setRunSummary({
      elapsedSec: 0,
      estimatedInputTokens: chunkToks + promptToks,
      estimatedOutputTokens: outToks,
      completedTypes: [],
    });
    sessionStorage.removeItem(summaryKey);
    runAnalysisInFlightRef.current = true;
    runAnalysisMut.mutate();
  }

  function handleDeleteOutputs() {
    if (window.confirm("Delete all analysis outputs for this topic?")) {
      clearSummary();
      deleteOutputsMut.mutate();
    }
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

        {!parseMut.isSuccess && isParsed && (
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
              <strong>Chapters:</strong> {chapters.length} ·{" "}
              <strong>Chunks preview:</strong> {chunks.length} shown below
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

        {/* Prerequisites */}
        {!boundProvider && (
          <div
            className="card-error"
            style={{
              padding: "0.5rem 0.75rem",
              marginBottom: "0.75rem",
              borderRadius: 4,
              fontSize: "0.9rem",
            }}
          >
            No provider bound. Bind a provider above first.
          </div>
        )}

        {!hasDoc && (
          <p className="text-dim" style={{ marginBottom: "0.75rem" }}>
            Upload and parse a document first.
          </p>
        )}

        {hasDoc && !isParsed && (
          <p className="text-dim" style={{ marginBottom: "0.75rem" }}>
            Parse the document before running analysis.
          </p>
        )}

        {/* Run controls */}
        {isParsed && (
          <div
            style={{
              background: "#fff8e1",
              padding: "0.75rem",
              borderRadius: 4,
              marginBottom: "0.75rem",
            }}
          >
            <p style={{ marginBottom: "0.5rem", fontSize: "0.85rem", color: "#f57f17" }}>
              Running analysis will call the LLM and may consume API credits.
            </p>
            <div
              style={{
                display: "flex",
                gap: "0.5rem",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <div>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    fontSize: "0.85rem",
                    marginBottom: "0.25rem",
                  }}
                >
                  Limit chunks:
                  <input
                    type="number"
                    min={1}
                    max={totalChunkCount || 1000}
                    value={limitChunks}
                    onChange={(e) => {
                      const v = Math.max(1, Number(e.target.value));
                      setLimitChunks(
                        totalChunkCount ? Math.min(v, totalChunkCount) : v
                      );
                    }}
                    style={{ width: 60 }}
                  />
                  {totalChunkCount > 0 && (
                    <span className="text-dim">
                      of {totalChunkCount} total chunks
                    </span>
                  )}
                </label>
                <p
                  className="text-dim"
                  style={{ fontSize: "0.78rem", lineHeight: 1.4, marginBottom: "0.5rem" }}
                >
                  How many chunks to analyze, starting from the beginning of the
                  novel. Each chunk is ~2,000 characters. Results from 6 analysis
                  types (overview, characters, relations, events, causality,
                  themes). Higher values give broader coverage but consume more
                  API tokens.
                </p>
                {totalChunkCount > 0 && (() => {
                  const selectedChunks = (allChunksMeta?.chunks ?? []).slice(
                    0,
                    limitChunks
                  );
                  const selectedChars = selectedChunks.reduce(
                    (s, c) => s + c.char_count,
                    0
                  );
                  const chunkTokens = Math.round(selectedChars / 3.5);
                  const promptTokens = 600 * 6;
                  const inputTokens = chunkTokens + promptTokens;
                  const outputTokens = 800 * 6;
                  return (
                    <div
                      style={{
                        background: "#fff",
                        border: "1px solid #ffe0b2",
                        borderRadius: 4,
                        padding: "0.5rem 0.75rem",
                        marginBottom: "0.5rem",
                        fontSize: "0.82rem",
                      }}
                    >
                      <p style={{ fontWeight: 600, marginBottom: "0.3rem" }}>
                        Estimated token usage:
                      </p>
                      <table
                        style={{
                          width: "100%",
                          borderCollapse: "collapse",
                          lineHeight: 1.5,
                        }}
                      >
                        <tbody>
                          <tr>
                            <td style={{ paddingRight: "0.75rem", color: "#666" }}>
                              Chunk text ({selectedChars.toLocaleString()} chars)
                            </td>
                            <td style={{ textAlign: "right" }}>
                              ~{chunkTokens.toLocaleString()} tokens
                            </td>
                          </tr>
                          <tr>
                            <td style={{ paddingRight: "0.75rem", color: "#666" }}>
                              System prompts (6 types × ~600)
                            </td>
                            <td style={{ textAlign: "right" }}>
                              ~{promptTokens.toLocaleString()} tokens
                            </td>
                          </tr>
                          <tr style={{ borderTop: "1px solid #eee" }}>
                            <td style={{ paddingRight: "0.75rem", fontWeight: 600 }}>
                              Total input
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 600 }}>
                              ~{inputTokens.toLocaleString()} tokens
                            </td>
                          </tr>
                          <tr>
                            <td style={{ paddingRight: "0.75rem", color: "#666" }}>
                              Estimated output (6 types × ~800)
                            </td>
                            <td style={{ textAlign: "right" }}>
                              ~{outputTokens.toLocaleString()} tokens
                            </td>
                          </tr>
                          <tr style={{ borderTop: "1px solid #eee" }}>
                            <td style={{ paddingRight: "0.75rem", fontWeight: 600 }}>
                              Grand total
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 600 }}>
                              ~{(inputTokens + outputTokens).toLocaleString()} tokens
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      <p
                        className="text-dim"
                        style={{
                          fontSize: "0.72rem",
                          marginTop: "0.35rem",
                          fontStyle: "italic",
                        }}
                      >
                        Rough estimate only — actual usage depends on chunk
                        content and JSON output size. Chars→tokens uses ~3.5
                        chars/token for mixed Chinese/English text.
                      </p>
                    </div>
                  );
                })()}
              </div>
              <button
                onClick={handleRunAnalysis}
                disabled={isAnalysisRunning || hasActiveJob}
              >
                {isAnalysisRunning || hasActiveJob
                  ? "Running..."
                  : "Run Analysis"}
              </button>
              {hasActiveJob && (
                <p className="text-dim" style={{ fontSize: "0.82rem", color: "#f57f17" }}>
                  Analysis is already running for this topic
                </p>
              )}
            </div>

            {runError && (
              <div
                className="card-error"
                style={{
                  padding: "0.4rem 0.6rem",
                  marginTop: "0.5rem",
                  borderRadius: 4,
                  fontSize: "0.85rem",
                }}
              >
                {runError}
              </div>
            )}

            {runAnalysisMut.isSuccess && (
              <div
                style={{
                  background: "#f0fff5",
                  padding: "0.5rem 0.75rem",
                  marginTop: "0.5rem",
                  borderRadius: 4,
                  fontSize: "0.88rem",
                  color: "#27ae60",
                }}
              >
                Analysis complete — {runAnalysisMut.data.count} outputs generated.
              </div>
            )}
          </div>
        )}

        {/* Progress bar */}
        {isAnalysisRunning && (
          <div
            style={{
              background: "#f0f4ff",
              border: "1px solid #c8d6ff",
              borderRadius: 6,
              padding: "0.75rem 1rem",
              marginBottom: "0.75rem",
            }}
          >
            <p style={{ fontWeight: 600, marginBottom: "0.4rem", fontSize: "0.9rem" }}>
              Analysis running...
              <span style={{ fontWeight: 400, color: "#888", marginLeft: "0.5rem" }}>
                {Math.floor(elapsedSec / 60)}m {elapsedSec % 60}s elapsed
              </span>
            </p>
            {(() => {
              const allOut = allOutputsData?.outputs ?? [];
              const completedTypes = new Set(allOut.map((o) => o.output_type));
              const done = ALL_TYPES.filter((t) => completedTypes.has(t));
              const progress = (done.length / ALL_TYPES.length) * 100;
              return (
                <>
                  <div
                    style={{
                      height: 8,
                      background: "#e0e0e0",
                      borderRadius: 4,
                      overflow: "hidden",
                      marginBottom: "0.4rem",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${progress}%`,
                        background:
                          progress < 30
                            ? "#4fc3f7"
                            : progress < 70
                              ? "#29b6f6"
                              : "#66bb6a",
                        borderRadius: 4,
                        transition: "width 0.5s ease",
                      }}
                    />
                  </div>
                  <p style={{ fontSize: "0.82rem", color: "#555" }}>
                    {done.length}/{ALL_TYPES.length} types completed
                    {done.length > 0 && (
                      <span style={{ marginLeft: "0.5rem" }}>
                        {ALL_TYPES.map((t) =>
                          completedTypes.has(t) ? (
                            <span
                              key={t}
                              style={{
                                color: "#27ae60",
                                marginRight: "0.4rem",
                              }}
                            >
                              ✓ {t}
                            </span>
                          ) : (
                            <span
                              key={t}
                              style={{
                                color: "#ccc",
                                marginRight: "0.4rem",
                              }}
                            >
                              ○ {t}
                            </span>
                          )
                        )}
                      </span>
                    )}
                  </p>
                </>
              );
            })()}
          </div>
        )}

        {/* Analysis summary bar */}
        {runSummary && !isAnalysisRunning && (
          <div
            style={{
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 6,
              padding: "0.75rem 1rem",
              marginBottom: "0.75rem",
            }}
          >
            <p
              style={{
                fontWeight: 600,
                fontSize: "0.9rem",
                marginBottom: "0.4rem",
                color: retryingType ? "#f57f17" : "#166534",
              }}
            >
              {retryingType
                ? `Re-analyzing ${retryingType}...`
                : "Analysis complete"}
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "0.25rem 1rem",
                fontSize: "0.83rem",
              }}
            >
              <p>
                <strong>Time:</strong>{" "}
                {retryingType
                  ? `${Math.floor(retryElapsed / 60)}m ${retryElapsed % 60}s`
                  : `${Math.floor(runSummary.elapsedSec / 60)}m ${runSummary.elapsedSec % 60}s`}
              </p>
              <p>
                <strong>Tokens:</strong>{" "}
                {runSummary.estimatedInputTokens.toLocaleString()} input +{" "}
                {runSummary.estimatedOutputTokens.toLocaleString()} output ={" "}
                {(
                  runSummary.estimatedInputTokens +
                  runSummary.estimatedOutputTokens
                ).toLocaleString()}{" "}
                total
              </p>
            </div>
            <div style={{ marginTop: "0.4rem", fontSize: "0.83rem" }}>
              {ALL_TYPES.map((t) => {
                const ok = runSummary.completedTypes.includes(t);
                return ok ? (
                  <span
                    key={t}
                    style={{
                      color: "#166534",
                      marginRight: "0.6rem",
                    }}
                  >
                    ✓ {t}
                    <button
                      onClick={() => handleRetryType(t, true)}
                      disabled={retryingType === t || isAnalysisRunning}
                      style={{
                        marginLeft: "0.3rem",
                        padding: "0.1em 0.4em",
                        fontSize: "0.72rem",
                        border: "1px solid #166534",
                        borderRadius: 3,
                        background: "#fff",
                        color: "#166534",
                        cursor: "pointer",
                      }}
                    >
                      {retryingType === t ? "Running..." : "Re-analyze"}
                    </button>
                  </span>
                ) : (
                  <span
                    key={t}
                    style={{
                      color: "#dc2626",
                      marginRight: "0.6rem",
                    }}
                  >
                    ✗ {t}
                    <span style={{ fontSize: "0.75rem", color: "#999" }}>
                      {" "}
                      — not generated
                    </span>
                    <button
                      onClick={() => handleRetryType(t, false)}
                      disabled={retryingType === t || isAnalysisRunning}
                      style={{
                        marginLeft: "0.3rem",
                        padding: "0.1em 0.4em",
                        fontSize: "0.72rem",
                        border: "1px solid #dc2626",
                        borderRadius: 3,
                        background: "#fff",
                        color: "#dc2626",
                        cursor: "pointer",
                      }}
                    >
                      {retryingType === t ? "Retrying..." : "Retry"}
                    </button>
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Outputs */}
        {(() => {
          const allOutputs = allOutputsData?.outputs ?? [];
          const rawOutputs = outputData?.outputs ?? [];
          const { latest: outputs, hiddenCounts } =
            groupLatestOutputs(rawOutputs);
          const totalOutputCount = allOutputs.length;
          const rawHasOutputs = totalOutputCount > 0;
          const typeCounts: Record<string, number> = {};
          for (const o of allOutputs) {
            typeCounts[o.output_type] =
              (typeCounts[o.output_type] ?? 0) + 1;
          }
          const hasOutputs = outputs.length > 0;
          const totalHidden = Object.values(hiddenCounts).reduce(
            (a, b) => a + b,
            0
          );
          const outputTypes = [
            "overview",
            "characters",
            "relations",
            "events",
            "causality",
            "themes",
          ];

          return (
            <>
              {rawHasOutputs && (
                <div
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    marginBottom: "0.75rem",
                    alignItems: "center",
                    flexWrap: "wrap",
                  }}
                >
                  <select
                    value={outputTypeFilter}
                    onChange={(e) => setOutputTypeFilter(e.target.value)}
                  >
                    <option value="">
                      All types ({totalOutputCount})
                    </option>
                    {outputTypes.map((t) => {
                      const cnt = typeCounts[t] ?? 0;
                      return (
                        <option key={t} value={t}>
                          {t} ({cnt})
                        </option>
                      );
                    })}
                  </select>
                  <button
                    className="btn-danger"
                    onClick={handleDeleteOutputs}
                    disabled={deleteOutputsMut.isPending}
                  >
                    {deleteOutputsMut.isPending
                      ? "Deleting..."
                      : "Delete All Outputs"}
                  </button>
                </div>
              )}

              {totalHidden > 0 && (
                <p
                  className="text-dim"
                  style={{
                    fontSize: "0.8rem",
                    marginBottom: "0.5rem",
                    fontStyle: "italic",
                  }}
                >
                  {totalHidden} older duplicate output
                  {totalHidden > 1 ? "s" : ""} hidden (
                  {Object.entries(hiddenCounts)
                    .filter(([, n]) => n > 0)
                    .map(([t, n]) => `${n}× ${t}`)
                    .join(", ")}
                  ).
                </p>
              )}

              {outputs.map((o) => (
                <AnalysisOutputCard key={o.id} output={o} />
              ))}

              {!hasOutputs && rawHasOutputs && (
                <p className="text-dim">
                  No outputs match this filter.{" "}
                  <button
                    onClick={() => setOutputTypeFilter("")}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#2563eb",
                      cursor: "pointer",
                      padding: 0,
                      fontSize: "inherit",
                      textDecoration: "underline",
                    }}
                  >
                    Show all
                  </button>
                </p>
              )}

              {!hasOutputs && isAnalysisRunning && !rawHasOutputs && (
                <p className="text-dim" style={{ color: "#f57f17" }}>
                  Analysis in progress... The backend is processing. Do not
                  refresh or navigate away — if you do, the progress bar will
                  persist and auto-detect completion.
                </p>
              )}

              {!hasOutputs && !isAnalysisRunning && !rawHasOutputs && (
                <p className="text-dim">
                  No analysis outputs yet. Run analysis to generate results.
                </p>
              )}
            </>
          );
        })()}
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
