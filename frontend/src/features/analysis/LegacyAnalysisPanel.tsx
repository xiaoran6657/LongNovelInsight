import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisOutput } from "../../api/types";
import AnalysisOutputCard from "../../components/AnalysisOutputCard";
import LoadingBlock from "../../components/LoadingBlock";
import {
  listAnalysisOutputs,
  runAnalysisAsync,
  deleteAnalysisOutputs,
  getAnalysisStatus,
  runSingleAnalysis,
} from "../../api/analysis";
import { getChunksMeta } from "../../api/parse";

const ALL_TYPES = ["overview", "characters", "relations", "events", "causality", "themes"];

interface TypeStat {
  runs: number;
  inputTokens: number;
  outputTokens: number;
  confidence: number | null;
}

interface RunSummary {
  elapsedSec: number;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  completedTypes: string[];
  typeStats: Record<string, TypeStat>;
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
    items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    latest.push(items[0]);
    if (items.length > 1) hiddenCounts[type] = items.length - 1;
  }
  latest.sort((a, b) => a.output_type.localeCompare(b.output_type));
  return { latest, hiddenCounts };
}

interface Props {
  topicId: string;
  hasDoc: boolean;
  isParsed: boolean;
  boundProvider: boolean;
}

export default function LegacyAnalysisPanel({ topicId, hasDoc, isParsed, boundProvider }: Props) {
  const qc = useQueryClient();
  const [limitChunks, setLimitChunks] = useState(5);
  const [runError, setRunError] = useState("");
  const [outputTypeFilter, setOutputTypeFilter] = useState("");
  const [retryingType, setRetryingType] = useState<string | null>(null);
  const [retryError, setRetryError] = useState("");
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);

  const { data: chunksMeta } = useQuery({
    queryKey: ["chunks-meta", topicId],
    queryFn: () => getChunksMeta(topicId),
    enabled: !!topicId && hasDoc,
  });
  const totalChunkCount = chunksMeta?.chunk_count ?? 0;
  const maxChunks = totalChunkCount || 1000;

  const { data: allOutputsData } = useQuery({
    queryKey: ["outputs", topicId],
    queryFn: () => listAnalysisOutputs(topicId),
    enabled: !!topicId,
  });

  const { data: jobStatus } = useQuery({
    queryKey: ["analysis-status", topicId],
    queryFn: () => getAnalysisStatus(topicId),
    enabled: !!topicId,
    refetchInterval: 3000,
  });

  const runAnalysisMut = useMutation({
    mutationFn: async () => {
      const start = Date.now();
      await runAnalysisAsync(topicId, limitChunks);
      let done = false;
      while (!done) {
        await new Promise((r) => setTimeout(r, 2000));
        const s = await getAnalysisStatus(topicId);
        const st = s?.latest_job?.status;
        if (st === "succeeded" || st === "failed" || st === "cancelled") {
          done = true;
          if (st === "failed") throw new Error(s.latest_job?.error_message ?? "Analysis job failed");
        }
      }
      const elapsedSec = Math.round((Date.now() - start) / 1000);
      const data = await listAnalysisOutputs(topicId);
      const outputs = data.outputs ?? [];
      const completed = outputs.map((o) => o.output_type);
      const realInput = outputs.reduce((s, o) => s + (o.prompt_tokens ?? 0), 0);
      const realOutput = outputs.reduce((s, o) => s + (o.completion_tokens ?? 0), 0);
      const typeStats: Record<string, TypeStat> = {};
      for (const o of outputs) {
        let conf: number | null = o.confidence > 0 ? o.confidence : null;
        if (!conf && o.content_json) {
          const items: number[] = [];
          for (const [, v] of Object.entries(o.content_json)) {
            if (Array.isArray(v)) for (const item of v) {
              if (item && typeof item === "object" && typeof (item as Record<string, unknown>).confidence === "number")
                items.push((item as Record<string, unknown>).confidence as number);
            }
          }
          if (items.length > 0) conf = items.reduce((a, b) => a + b, 0) / items.length;
        }
        typeStats[o.output_type] = { runs: 1, inputTokens: o.prompt_tokens ?? 0, outputTokens: o.completion_tokens ?? 0, confidence: conf };
      }
      for (const t of ALL_TYPES) { if (!typeStats[t]) typeStats[t] = { runs: 0, inputTokens: 0, outputTokens: 0, confidence: null }; }
      const summary: RunSummary = { elapsedSec, estimatedInputTokens: realInput, estimatedOutputTokens: realOutput, completedTypes: completed, typeStats };
      setRunSummary(summary);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
      qc.invalidateQueries({ queryKey: ["topic", topicId] });
      qc.invalidateQueries({ queryKey: ["analysis-status", topicId] });
      setRunError("");
    },
    onError: (err: Error) => {
      setRunSummary(null);
      setRunError(err.message);
    },
  });

  const deleteOutputsMut = useMutation({
    mutationFn: () => deleteAnalysisOutputs(topicId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
      qc.invalidateQueries({ queryKey: ["topic", topicId] });
    },
  });

  const retrySingleMut = useMutation({
    mutationFn: ({ outputType, deepen }: { outputType: string; deepen: boolean }) =>
      runSingleAnalysis(topicId, outputType, limitChunks, deepen),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outputs", topicId] });
      setRetryingType(null);
      setRetryError("");
    },
    onError: (err: Error) => {
      setRetryingType(null);
      setRetryError(err.message);
    },
  });

  const allOutputs = allOutputsData?.outputs ?? [];
  const { latest: latestOutputs, hiddenCounts } = groupLatestOutputs(allOutputs);
  const filteredOutputs = outputTypeFilter
    ? allOutputs.filter((o) => o.output_type === outputTypeFilter)
    : latestOutputs;

  const activeJob = jobStatus?.latest_job;
  const isRunning = activeJob?.status === "pending" || activeJob?.status === "running";

  return (
    <div>
      <h2>Analysis (v1 Legacy)</h2>

      {!boundProvider && (
        <div className="card"><p className="text-dim">No provider bound. Bind a provider above first.</p></div>
      )}
      {hasDoc && !isParsed && <p className="text-dim">Parse the document before running analysis.</p>}

      {isParsed && boundProvider && (
        <div className="card" style={{ background: "#fff8e1", borderRadius: 4 }}>
          <p style={{ fontSize: "0.85rem", color: "#f57f17", marginBottom: "0.5rem" }}>
            Running analysis will call the LLM and may consume API credits.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.85rem" }}>
              Limit chunks:
              <input type="number" min={1} max={maxChunks} value={limitChunks}
                onChange={(e) => { const v = Math.max(1, Number(e.target.value)); setLimitChunks(totalChunkCount ? Math.min(v, totalChunkCount) : v); }}
                style={{ width: 60 }} />
              {totalChunkCount > 0 && <span className="text-dim">of {totalChunkCount} total chunks</span>}
            </label>
            <button onClick={() => runAnalysisMut.mutate()} disabled={runAnalysisMut.isPending || isRunning}>
              {runAnalysisMut.isPending ? "Running..." : isRunning ? "Job in progress..." : "Run v1 Analysis"}
            </button>
          </div>
          {totalChunkCount > 0 && (
            <p className="text-dim" style={{ fontSize: "0.78rem", marginTop: "0.5rem" }}>
              Est. ~{limitChunks} chunks × 6 types ≈ {(limitChunks * 6 * 3000).toLocaleString()} tokens
            </p>
          )}
          {runError && <p className="field-error">{runError}</p>}
          {retryError && <p className="field-error" style={{ marginTop: "0.25rem" }}>{retryError}</p>}
        </div>
      )}

      {isRunning && <LoadingBlock text="Analysis running... polling status" />}

      {runSummary && (
        <div className="card" style={{ background: "#e8f5e9" }}>
          <h4>Analysis Complete</h4>
          <p>Elapsed: {runSummary.elapsedSec}s · Input: {runSummary.estimatedInputTokens.toLocaleString()} tokens · Output: {runSummary.estimatedOutputTokens.toLocaleString()} tokens</p>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {ALL_TYPES.map((t) => {
              const s = runSummary.typeStats[t];
              const ok = s && s.runs > 0;
              return (
                <span key={t} style={{ fontSize: "0.78rem", padding: "0.15rem 0.4rem", borderRadius: 3, background: ok ? "#c8e6c9" : "#ffcdd2" }}>
                  {t}: {ok ? `${s.confidence != null ? (s.confidence * 100).toFixed(0) + "%" : "done"}` : "failed"}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {allOutputs.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <h3 style={{ margin: 0 }}>Outputs ({allOutputs.length})</h3>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <select value={outputTypeFilter} onChange={(e) => setOutputTypeFilter(e.target.value)}>
                <option value="">All types</option>
                {ALL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <button onClick={() => { if (confirm("Delete all analysis outputs?")) deleteOutputsMut.mutate(); }}
                disabled={deleteOutputsMut.isPending} style={{ background: "#e74c3c", fontSize: "0.78rem" }}>
                Delete All
              </button>
            </div>
          </div>
          {filteredOutputs.map((o) => (
            <div key={o.id} style={{ marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{o.output_type}</strong>
                <button onClick={() => { setRetryingType(o.output_type); setRetryError(""); retrySingleMut.mutate({ outputType: o.output_type, deepen: false }); }}
                  disabled={retryingType === o.output_type}
                  style={{ fontSize: "0.75rem", padding: "0.1em 0.4em" }}>
                  {retryingType === o.output_type ? "Retrying..." : "Retry"}
                </button>
              </div>
              <AnalysisOutputCard output={o} />
              {hiddenCounts[o.output_type] > 0 && (
                <p className="text-dim" style={{ fontSize: "0.75rem" }}>
                  +{hiddenCounts[o.output_type]} older version(s) — use filter to view
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
