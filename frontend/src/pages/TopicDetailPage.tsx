import { useState, useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import LoadingBlock from "../components/LoadingBlock";
import ErrorBlock from "../components/ErrorBlock";
import {
  getTopic,
  bindProvider,
  getEffectiveConfig,
  getTopicProviderConfig,
  updateTopicProviderConfig,
} from "../api/topics";
import { listProviders, listProviderPresets } from "../api/providers";
import { getCurrentDocument } from "../api/documents";
import { listChapters, listChunks, getChunksMeta } from "../api/parse";
import TopicHeader from "../features/topic/TopicHeader";
import ProviderBindingPanel from "../features/topic/ProviderBindingPanel";
import DocumentPanel from "../features/topic/DocumentPanel";
import ParsePanel from "../features/topic/ParsePanel";
import ChaptersPanel from "../features/topic/ChaptersPanel";
import EpubChapterTree from "../features/topic/EpubChapterTree";
import SourceLocatorBadge from "../features/topic/SourceLocatorBadge";
import StoragePanel from "../features/topic/StoragePanel";
import TopicSearchPanel from "../features/search/TopicSearchPanel";
import ChunksMetaPanel from "../features/analysis/ChunksMetaPanel";
import ChunkRangeSelector from "../features/analysis/ChunkRangeSelector";
import type { ChunkRange } from "../features/analysis/ChunkRangeSelector";
import type { AnalysisMode } from "../api/types";
import LegacyAnalysisPanel from "../features/analysis/LegacyAnalysisPanel";
import AnalysisRunPanel from "../features/analysis/AnalysisRunPanel";
import AnalysisRunHistory from "../features/analysis/AnalysisRunHistory";
import AnalysisOutputsPanel from "../features/analysis/AnalysisOutputsPanel";
import EntityEvidencePanel from "../features/evidence/EntityEvidencePanel";
import SimilarScenesPanel from "../features/evidence/SimilarScenesPanel";
import { useActiveRunPersistence } from "../features/analysis/useActiveRunPersistence";

export default function TopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const queryClient = useQueryClient();
  const [showChunkText, setShowChunkText] = useState(false);
  const [chunkRange, setChunkRange] = useState<ChunkRange>({ mode: "chunk", start: null, end: null });
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("preview");
  const [previewLimitChunks, setPreviewLimitChunks] = useState(3);
  const { activeRunId, setActiveRunId, clearStorage } = useActiveRunPersistence(topicId ?? "");

  // Clear topic-scoped UI state when topic changes.
  // activeRunId is managed by useActiveRunPersistence (re-reads sessionStorage on topic change).
  const prevTopicIdRef = useRef(topicId);
  useEffect(() => {
    if (prevTopicIdRef.current !== topicId) {
      prevTopicIdRef.current = topicId;
      setChunkRange({ mode: "chunk", start: null, end: null });
      setAnalysisMode("preview");
      setPreviewLimitChunks(3);
    }
  }, [topicId]);

  // Provider binding state
  const [bindProviderId, setBindProviderId] = useState("");
  const [bindError, setBindError] = useState("");

  // Topic-level config editing
  const [editModel, setEditModel] = useState("");
  const [editMaxTokens, setEditMaxTokens] = useState("");
  const [editTemp, setEditTemp] = useState("");
  const [editThinking, setEditThinking] = useState("");
  const [editParallel, setEditParallel] = useState("");
  const [configDirty, setConfigDirty] = useState(false);
  const [configSaveError, setConfigSaveError] = useState("");
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});

  function validateConfig(): boolean {
    const errs: Record<string, string> = {};
    if (editMaxTokens && (isNaN(Number(editMaxTokens)) || Number(editMaxTokens) < 512))
      errs.maxTokens = "Minimum 512 tokens";
    if (editTemp) {
      const t = Number(editTemp);
      if (isNaN(t) || t < 0 || t > 2) errs.temp = "Must be 0–2";
    }
    if (editParallel) {
      const p = Number(editParallel);
      if (isNaN(p) || p < 1 || p > 6) errs.parallel = "Must be 1–6";
    }
    setConfigErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleSaveConfig() {
    if (!validateConfig()) return;
    saveConfigMut.mutate();
  }

  function markDirty(field?: string) {
    if (!configDirty) setConfigDirty(true);
    setConfigSaveError("");
    if (field && configErrors[field]) {
      setConfigErrors((prev) => {
        const n = { ...prev };
        delete n[field];
        return n;
      });
    }
  }

  function applyPreset(model: string, maxTok: number, temp: number, thinking: string, parallel: number) {
    setEditModel(model);
    setEditMaxTokens(String(maxTok));
    setEditTemp(String(temp));
    setEditThinking(thinking);
    setEditParallel(String(parallel));
    setConfigDirty(true);
    setConfigSaveError("");
  }

  // ── Queries ──

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

  const { data: effectiveConfig } = useQuery({
    queryKey: ["effective-config", topicId],
    queryFn: () => getEffectiveConfig(topicId!),
    enabled: !!topicId,
  });

  const { data: storedConfigData } = useQuery({
    queryKey: ["provider-config", topicId],
    queryFn: () => getTopicProviderConfig(topicId!),
    enabled: !!topicId,
  });

  const { data: presetData } = useQuery({
    queryKey: ["provider-presets"],
    queryFn: listProviderPresets,
  });

  const activePresetModels =
    presetData?.presets.find((pr) => pr.provider_key === effectiveConfig?.provider_key)?.models ?? [];

  useEffect(() => {
    const stored = storedConfigData?.config;
    if (!effectiveConfig) return;
    setEditModel(stored?.model_name_override || "");
    setEditMaxTokens(stored?.max_output_tokens_override?.toString() || "");
    setEditTemp(stored?.temperature_override?.toString() || "");
    setEditThinking(stored?.thinking_mode_override || "");
    setEditParallel(stored?.analysis_parallelism_override?.toString() || "");
    setConfigDirty(false);
    setConfigSaveError("");
  }, [effectiveConfig, storedConfigData]);

  const saveConfigMut = useMutation({
    mutationFn: () =>
      updateTopicProviderConfig(topicId!, {
        model_name_override: editModel || null,
        max_output_tokens_override: editMaxTokens ? Number(editMaxTokens) : null,
        temperature_override: editTemp ? Number(editTemp) : null,
        thinking_mode_override: editThinking || null,
        analysis_parallelism_override: editParallel ? Number(editParallel) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["effective-config", topicId] });
      queryClient.invalidateQueries({ queryKey: ["provider-config", topicId] });
      setConfigDirty(false);
      setConfigSaveError("");
    },
    onError: (err: Error) => setConfigSaveError(err.message),
  });

  const bindMut = useMutation({
    mutationFn: (providerId: string) => bindProvider(topicId!, providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      queryClient.invalidateQueries({ queryKey: ["effective-config", topicId] });
      setBindError("");
      setBindProviderId("");
    },
    onError: (err: Error) => setBindError(err.message),
  });

  const { data: doc, isLoading: docLoading, isError: docError, error: docErr } = useQuery({
    queryKey: ["document", topicId],
    queryFn: () => getCurrentDocument(topicId!),
    enabled: !!topicId,
    retry: false,
  });

  const hasDoc = !!doc && !docError && !("detail" in (doc as unknown as object));

  const { data: chapterData } = useQuery({
    queryKey: ["chapters", topicId],
    queryFn: () => listChapters(topicId!),
    enabled: !!topicId && hasDoc,
  });

  const { data: chunksMeta } = useQuery({
    queryKey: ["chunks-meta", topicId],
    queryFn: () => getChunksMeta(topicId!),
    enabled: !!topicId && hasDoc,
  });

  const { data: chunkData } = useQuery({
    queryKey: ["chunks", topicId, showChunkText],
    queryFn: () => listChunks(topicId!, { include_text: showChunkText, limit: 20 }),
    enabled: !!topicId && hasDoc,
  });

  const chunks = chunkData?.chunks ?? [];
  const providers = providerData?.providers ?? [];
  const boundProvider = providers.find((p) => p.id === topic?.provider_id);

  if (topicLoading) return <LoadingBlock text="Loading topic..." />;
  if (topicError) return <ErrorBlock message={topicErr?.message ?? "Failed to load topic"} />;
  if (!topic) return <ErrorBlock message="Topic not found" />;

  return (
    <div>
      <TopicHeader topic={topic} />

      <ProviderBindingPanel
        providers={providers}
        effectiveConfig={effectiveConfig}
        activePresetModels={activePresetModels}
        boundProvider={boundProvider}
        bindProviderId={bindProviderId}
        bindError={bindError}
        bindPending={bindMut.isPending}
        onBindProviderIdChange={(v) => { setBindProviderId(v); setBindError(""); }}
        onBind={() => bindProviderId && bindMut.mutate(bindProviderId)}
        editModel={editModel}
        editMaxTokens={editMaxTokens}
        editTemp={editTemp}
        editThinking={editThinking}
        editParallel={editParallel}
        configDirty={configDirty}
        configSaveError={configSaveError}
        configErrors={configErrors}
        savePending={saveConfigMut.isPending}
        onEditModel={(v) => { setEditModel(v); markDirty("model"); }}
        onEditMaxTokens={(v) => { setEditMaxTokens(v); markDirty("maxTokens"); }}
        onEditTemp={(v) => { setEditTemp(v); markDirty("temp"); }}
        onEditThinking={(v) => { setEditThinking(v); markDirty(); }}
        onEditParallel={(v) => { setEditParallel(v); markDirty("parallel"); }}
        onSaveConfig={handleSaveConfig}
        onApplyPreset={applyPreset}
      />

      <DocumentPanel
        topicId={topic.id}
        document={doc}
        docLoading={docLoading}
        docError={docErr as Error | null}
      />

      <ParsePanel topicId={topic.id} hasDocument={hasDoc} />
      <ChunksMetaPanel topicId={topic.id} hasDoc={hasDoc} />
      {chunksMeta && (
        <ChunkRangeSelector meta={chunksMeta} value={chunkRange} onChange={setChunkRange} />
      )}
      <ChaptersPanel chapters={chapterData?.chapters} />
      {doc?.file_type === "epub" && chapterData?.chapters && chapterData.chapters.length > 0 && (
        <EpubChapterTree chapters={chapterData.chapters} />
      )}

      {showChunkText && chunks.length > 0 && (
        <div className="card">
          <h3>Chunk Preview</h3>
          {chunks.slice(0, 5).map((c) => (
            <div key={c.id} style={{ marginBottom: "0.5rem", padding: "0.5rem", background: "#f9f9f9", borderRadius: 4 }}>
              <p className="text-dim" style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                <span>Ch. {c.chapter_index} chunk {c.chunk_index} ({c.char_count} chars)</span>
                <SourceLocatorBadge
                  sourceLocatorJson={c.source_locator_json}
                  fileType={doc?.file_type}
                  chapterIndex={c.chapter_index}
                  chunkIndex={c.chunk_index}
                />
              </p>
              <p style={{ fontSize: "0.8rem", maxHeight: 100, overflow: "hidden" }}>{c.text}</p>
            </div>
          ))}
        </div>
      )}
      <button onClick={() => setShowChunkText(!showChunkText)} style={{ fontSize: "0.8rem", marginBottom: "0.5rem" }}>
        {showChunkText ? "Hide chunk text" : "Show chunk text"}
      </button>

      <StoragePanel topicId={topic.id} />

      <TopicSearchPanel
        topicId={topic.id}
      />

      <AnalysisRunPanel
        topicId={topic.id}
        meta={chunksMeta}
        mode={analysisMode}
        limitChunks={previewLimitChunks}
        range={chunkRange}
        hasDoc={hasDoc}
        isParsed={doc?.status === "parsed"}
        boundProvider={!!boundProvider}
        effectiveConfig={effectiveConfig}
        activeRunId={activeRunId}
        onActiveRunIdChange={setActiveRunId}
        onChangeMode={setAnalysisMode}
        onChangeLimitChunks={setPreviewLimitChunks}
        onRunTerminal={clearStorage}
      />

      <AnalysisRunHistory
        topicId={topic.id}
        activeRunId={activeRunId}
        onSelectRun={setActiveRunId}
      />

      <AnalysisOutputsPanel
        topicId={topic.id}
        runId={activeRunId}
      />

      <EntityEvidencePanel topicId={topic.id} />

      <SimilarScenesPanel topicId={topic.id} />

      <LegacyAnalysisPanel
        topicId={topic.id}
        hasDoc={hasDoc}
        isParsed={doc?.status === "parsed"}
        boundProvider={!!boundProvider}
      />

      <div className="card">
        <h3>Chat</h3>
        <p><Link to={`/topics/${topic.id}/chat`}>Open chat &rarr;</Link></p>
      </div>
    </div>
  );
}
