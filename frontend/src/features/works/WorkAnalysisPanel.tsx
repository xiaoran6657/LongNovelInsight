import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { parseWork, createWorkAnalysisRun } from "../../api/works";
import LoadingBlock from "../../components/LoadingBlock";
import type { WorkItem } from "../../api/types";

type Props = {
  work: WorkItem;
  onRunCreated: (runId: string) => void;
};

export default function WorkAnalysisPanel({ work, onRunCreated }: Props) {
  const queryClient = useQueryClient();
  const [showAnalysisConfirm, setShowAnalysisConfirm] = useState(false);

  const parseMut = useMutation({
    mutationFn: () => parseWork(work.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works", work.topic_id] });
    },
  });

  const analysisMut = useMutation({
    mutationFn: () =>
      createWorkAnalysisRun(work.id, {
        mode: "preview",
        limit_chunks: 3,
        requested_types: ["characters"],
      }),
    onSuccess: (data) => {
      setShowAnalysisConfirm(false);
      queryClient.invalidateQueries({ queryKey: ["works", work.topic_id] });
      queryClient.invalidateQueries({ queryKey: ["analysisRuns", work.topic_id] });
      onRunCreated(data.run.id);
    },
  });

  if (work.status === "empty") {
    return (
      <p className="text-dim" style={{ fontSize: "0.8rem" }}>
        Upload a document to enable parsing and analysis.
      </p>
    );
  }

  return (
    <div style={{ marginBottom: "0.5rem" }}>
      <h4 style={{ margin: "0 0 0.3rem 0" }}>Analysis</h4>

      {/* Parse */}
      {work.status === "uploaded" && (
        <div style={{ marginBottom: "0.4rem" }}>
          <button
            onClick={() => parseMut.mutate()}
            disabled={parseMut.isPending}
            style={{ fontSize: "0.8rem" }}
          >
            {parseMut.isPending ? "Parsing..." : "Parse Document"}
          </button>
          {parseMut.isError && (
            <p style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.2rem" }}>
              {(parseMut.error as Error)?.message || "Parse failed"}
            </p>
          )}
        </div>
      )}

      {parseMut.isPending && <LoadingBlock text="Parsing document..." />}

      {/* Analysis run */}
      {(work.status === "parsed" || work.status === "analyzed") && (
        <div style={{ marginBottom: "0.4rem" }}>
          {!showAnalysisConfirm && (
            <button
              onClick={() => setShowAnalysisConfirm(true)}
              disabled={analysisMut.isPending}
              style={{ fontSize: "0.8rem" }}
            >
              {analysisMut.isPending ? "Starting..." : "Run Preview Analysis"}
            </button>
          )}
          <p className="text-dim" style={{ fontSize: "0.7rem", marginTop: "0.2rem" }}>
            Runs a preview analysis (3 chunks) on the Work's document.
            For full analysis, use the Overview tab.
          </p>
          {showAnalysisConfirm && (
            <div
              className="card"
              style={{ marginTop: "0.4rem", background: "#fff8e1", fontSize: "0.8rem" }}
            >
              <p style={{ color: "#e65100", fontWeight: 600 }}>
                Confirm LLM preview analysis?
              </p>
              <p className="text-dim" style={{ marginTop: "0.25rem" }}>
                This sends up to 3 chunks from &quot;{work.title}&quot; to the configured
                LLM and may consume API credits.
              </p>
              <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.4rem" }}>
                <button
                  onClick={() => analysisMut.mutate()}
                  disabled={analysisMut.isPending}
                  aria-label="Confirm preview analysis"
                  style={{ fontSize: "0.8rem" }}
                >
                  {analysisMut.isPending ? "Starting..." : "Confirm Preview Analysis"}
                </button>
                <button
                  onClick={() => setShowAnalysisConfirm(false)}
                  disabled={analysisMut.isPending}
                  style={{ fontSize: "0.8rem" }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
          {analysisMut.isError && (
            <p style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.2rem" }}>
              {(analysisMut.error as Error)?.message || "Analysis run failed"}
            </p>
          )}
        </div>
      )}

      {analysisMut.isPending && <LoadingBlock text="Starting analysis run..." />}
    </div>
  );
}
