import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisMode, ChunksMetaResponse } from "../../api/types";
import { listAnalysisRuns, retryFailedAnalysisRun, resumeAnalysisRun } from "../../api/analysis";
import { ApiError } from "../../api/client";
import type { ChunkRange } from "./ChunkRangeSelector";
import { rangeToSelectionParams } from "./ChunkRangeSelector";
import { estimateTokens } from "./analysisSelection";
import { useAnalysisRun, useCreateAnalysisRun, isRunActive, isRunTerminal, runProgressPercent } from "./useAnalysisRun";
import AnalysisModeSelector from "./AnalysisModeSelector";
import AnalysisCostProjection from "./AnalysisCostProjection";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";
import StatusBadge from "../../components/StatusBadge";
import AnalysisStageProgress from "./AnalysisStageProgress";
import EffectiveProviderConfigCard from "../provider/EffectiveProviderConfigCard";
import type { EffectiveProviderConfig } from "../../api/types";

interface Props {
  topicId: string;
  meta: ChunksMetaResponse | undefined;
  mode: AnalysisMode;
  limitChunks: number;
  range: ChunkRange;
  hasDoc: boolean;
  isParsed: boolean;
  boundProvider: boolean;
  effectiveConfig: EffectiveProviderConfig | undefined;
  activeRunId: string | null;
  onActiveRunIdChange: (runId: string | null) => void;
  onChangeMode: (m: AnalysisMode) => void;
  onChangeLimitChunks: (n: number) => void;
  onRunTerminal?: () => void;
}

export default function AnalysisRunPanel({
  topicId, meta, mode, limitChunks, range,
  hasDoc, isParsed, boundProvider,
  effectiveConfig, activeRunId, onActiveRunIdChange,
  onChangeMode, onChangeLimitChunks,
  onRunTerminal,
}: Props) {
  const qc = useQueryClient();
  const [runError, setRunError] = useState("");
  const [showFullConfirm, setShowFullConfirm] = useState(false);

  const createMut = useCreateAnalysisRun(topicId);
  const { runQuery, cancelMut } = useAnalysisRun(activeRunId, topicId);
  const run = runQuery.data;

  const { data: runsData } = useQuery({
    queryKey: ["analysisRuns", topicId],
    queryFn: () => listAnalysisRuns(topicId),
    enabled: !!topicId,
  });

  const previousRun = runsData?.runs?.[0];
  const hasPreviousRun = !!previousRun;

  const retryMut = useMutation({
    mutationFn: (runId: string) => retryFailedAnalysisRun(runId),
    onSuccess: (_data, runId) => {
      qc.invalidateQueries({ queryKey: ["analysisRun", runId] });
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
    },
  });

  const resumeMut = useMutation({
    mutationFn: (runId: string) => resumeAnalysisRun(runId, true),
    onSuccess: (_data, runId) => {
      qc.invalidateQueries({ queryKey: ["analysisRun", runId] });
      qc.invalidateQueries({ queryKey: ["analysisRuns", topicId] });
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
    },
  });

  const configReady = effectiveConfig?.is_ready ?? false;
  const canRun = boundProvider && isParsed && hasDoc && configReady;

  function handleCreate() {
    if (mode === "full" && !showFullConfirm) {
      setShowFullConfirm(true);
      return;
    }
    setShowFullConfirm(false);
    setRunError("");

    const rangeParams = mode === "range" ? rangeToSelectionParams(range) : {};
    const body = {
      mode,
      requested_types: ["overview", "characters", "relations", "events", "causality", "themes"],
      limit_chunks: mode === "preview" ? limitChunks : undefined,
      ...rangeParams,
    };

    createMut.mutate(body, {
      onSuccess: (data) => {
        onActiveRunIdChange(data.run.id);
        setRunError("");
      },
      onError: (err: Error) => {
        setRunError(err.message);
      },
    });
  }

  const rangeInvalid = mode === "range" && (range.start == null || range.end == null || range.start > range.end);
  const est = meta ? estimateTokens(meta, mode, limitChunks, range) : null;
  const pct = runProgressPercent(run?.run);
  const terminal = isRunTerminal(run?.run.status);
  const active = isRunActive(run?.run.status);

  // Notify parent when run reaches terminal state (for sessionStorage cleanup)
  const prevTerminalRef = useRef(false);
  useEffect(() => {
    if (run && terminal && !prevTerminalRef.current) {
      onRunTerminal?.();
    }
    prevTerminalRef.current = !!terminal;
  }, [terminal, run, onRunTerminal]);

  // Auto-clear on 404 (run no longer exists on backend)
  useEffect(() => {
    if (runQuery.isError && runQuery.error instanceof ApiError && runQuery.error.status === 404) {
      onActiveRunIdChange(null);
    }
  }, [runQuery.isError, runQuery.error, onActiveRunIdChange]);

  function runStatusTone(status: string): "ok" | "warn" | "error" | "info" | "neutral" {
    switch (status) {
      case "succeeded": return "ok";
      case "running": return "info";
      case "partial_success": return "warn";
      case "failed": return "error";
      case "cancelled": return "neutral";
      default: return "neutral";
    }
  }

  return (
    <div>
      <h2>Analysis (v2)</h2>

      {!canRun && (
        <div className="card">
          <p className="text-dim">
            {!boundProvider ? "Bind a provider first." :
             !hasDoc ? "Upload and parse a document first." :
             "Parse the document to enable analysis."}
          </p>
        </div>
      )}

      {boundProvider && (
        <EffectiveProviderConfigCard config={effectiveConfig} />
      )}

      {boundProvider && !configReady && (
        <div className="card" style={{ background: "#fff3e0", fontSize: "0.82rem" }}>
          <p style={{ color: "#e65100", fontWeight: 600, marginBottom: "0.25rem" }}>
            Provider config is incomplete.
          </p>
          <p className="text-dim">
            Configure the provider above (model, API key, base URL) before running analysis.
          </p>
        </div>
      )}

      {canRun && meta && (
        <>
          <AnalysisModeSelector
            mode={mode} limitChunks={limitChunks}
            totalChunks={meta.chunk_count}
            hasPreviousRun={hasPreviousRun}
            onChangeMode={(m) => { onChangeMode(m); setShowFullConfirm(false); }}
            onChangeLimitChunks={onChangeLimitChunks}
          />

          {est && est.selectedChunks > 0 && (
            <AnalysisCostProjection {...est} />
          )}

          <div className="card" style={{ background: "#fff8e1", borderRadius: 4 }}>
            <p style={{ fontSize: "0.85rem", color: "#f57f17", marginBottom: "0.5rem" }}>
              Running v2 analysis will call the LLM and may consume API credits.
            </p>

            {mode === "full" && showFullConfirm && (
              <div style={{ marginBottom: "0.5rem", padding: "0.5rem", background: "#ffebee", borderRadius: 4 }}>
                <p style={{ fontWeight: 700, color: "#c62828", fontSize: "0.85rem" }}>
                  Confirm full analysis of ALL {meta.chunk_count} chunks?
                </p>
                <p className="text-dim" style={{ fontSize: "0.78rem" }}>
                  This will process every chunk and may consume significant API credits.
                </p>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.35rem" }}>
                  <button onClick={handleCreate} style={{ background: "#c62828" }}
                    aria-label="Confirm full analysis of all chunks">
                    Yes, run full analysis
                  </button>
                  <button onClick={() => setShowFullConfirm(false)}>Cancel</button>
                </div>
              </div>
            )}

            {mode === "range" && rangeInvalid && (
              <p className="field-error" style={{ marginBottom: "0.35rem" }}>
                Range selection is invalid: start must be ≤ end and both values must be set.
              </p>
            )}
            {(!showFullConfirm || mode !== "full") && (
              <button onClick={handleCreate} disabled={createMut.isPending || active || rangeInvalid}
                aria-label="Start v2 analysis run">
                {createMut.isPending ? "Creating..." : active ? "Run in progress..." : "Run v2 Analysis"}
              </button>
            )}
            {runError && <p className="field-error" style={{ marginTop: "0.35rem" }}>{runError}</p>}
          </div>
        </>
      )}

      {/* Polling error */}
      {activeRunId && runQuery.isError && (
        <ErrorBlock
          title="Failed to load run status"
          message={runQuery.error?.message ?? "Failed to load run status"}
          status={runQuery.error instanceof ApiError ? runQuery.error.status : undefined}
          detail={runQuery.error instanceof ApiError ? runQuery.error.detail : undefined}
          onRetry={() => runQuery.refetch()}
        />
      )}

      {/* Status display */}
      {run && (
        <div className="card" style={{
          background: terminal
            ? run.run.status === "succeeded" ? "#e8f5e9" : run.run.status === "partial_success" ? "#fff3e0" : "#ffebee"
            : "#e3f2fd",
          borderRadius: 4,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <h3 style={{ margin: 0 }}>
              Run{" "}
              <StatusBadge label={run.run.status} tone={runStatusTone(run.run.status)} />
            </h3>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              {active && (
                <button onClick={() => cancelMut.mutate()} disabled={cancelMut.isPending}
                  style={{ fontSize: "0.78rem", background: "#e74c3c" }}
                  aria-label="Cancel current analysis run">
                  {cancelMut.isPending ? "Cancelling..." : "Cancel"}
                </button>
              )}
              <span className="text-dim" style={{ fontSize: "0.8rem" }}>
                {active && !terminal ? "Polling..." : terminal ? "Complete" : ""}
              </span>
            </div>
          </div>

          {runQuery.isLoading && <LoadingBlock text="Loading run status..." />}

          {!terminal && active && (
            <div style={{ marginBottom: "0.5rem" }}>
              <div style={{ height: 6, background: "#e0e0e0", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${pct}%`, background: "#1976d2", transition: "width 0.3s" }} />
              </div>
              <p className="text-dim" style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}>
                {run.run.progress_current} / {run.run.progress_total} ({pct}%)
              </p>
            </div>
          )}

          <AnalysisStageProgress run={run} />

          {run.run.total_tokens > 0 && (
            <p className="text-dim" style={{ fontSize: "0.78rem", marginTop: "0.35rem" }}>
              Tokens: {run.run.total_tokens.toLocaleString()} · Model: {run.run.model_used || "—"}
            </p>
          )}

          {/* Inline retry/resume for partial_success or failed */}
          {(run.run.status === "partial_success" || run.run.status === "failed") && (
            <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.5rem" }}>
              <button
                onClick={() => retryMut.mutate(run.run.id)}
                disabled={retryMut.isPending}
                style={{ fontSize: "0.78rem" }}
                aria-label="Retry failed extractions for this run"
              >
                {retryMut.isPending ? "Retrying..." : "Retry Failed"}
              </button>
              <button
                onClick={() => resumeMut.mutate(run.run.id)}
                disabled={resumeMut.isPending}
                style={{ fontSize: "0.78rem" }}
                aria-label="Resume this run"
              >
                {resumeMut.isPending ? "Resuming..." : "Resume"}
              </button>
            </div>
          )}

          {run.run.error_message && (
            <p className="field-error" style={{ marginTop: "0.35rem", fontSize: "0.8rem" }}>{run.run.error_message}</p>
          )}
        </div>
      )}
    </div>
  );
}
