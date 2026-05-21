import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import LoadingBlock from "../../components/LoadingBlock";
import {
  listAnalysisOutputs,
  runAnalysisAsync,
  getAnalysisStatus,
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

  const allOutputs = allOutputsData?.outputs ?? [];

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
        <div className="card" style={{ fontSize: "0.82rem" }}>
          <p className="text-dim">
            {allOutputs.length} output(s) available. See the <strong>Outputs</strong> section above for details.
          </p>
        </div>
      )}
    </div>
  );
}
