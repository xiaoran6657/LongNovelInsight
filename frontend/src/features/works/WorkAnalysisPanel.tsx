import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parseWork, createWorkAnalysisRun } from "../../api/works";
import LoadingBlock from "../../components/LoadingBlock";
import type { WorkItem } from "../../api/types";

interface Props {
  work: WorkItem;
}

export default function WorkAnalysisPanel({ work }: Props) {
  const queryClient = useQueryClient();

  const parseMut = useMutation({
    mutationFn: () => parseWork(work.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });

  const analysisMut = useMutation({
    mutationFn: () =>
      createWorkAnalysisRun(work.id, {
        mode: "preview",
        limit_chunks: 3,
        requested_types: ["characters"],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
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
      {work.status === "parsed" && (
        <div style={{ marginBottom: "0.4rem" }}>
          <button
            onClick={() => analysisMut.mutate()}
            disabled={analysisMut.isPending}
            style={{ fontSize: "0.8rem" }}
          >
            {analysisMut.isPending ? "Starting..." : "Run Preview Analysis"}
          </button>
          <p className="text-dim" style={{ fontSize: "0.7rem", marginTop: "0.2rem" }}>
            Runs a preview analysis (3 chunks) on the Work's document.
            For full analysis, use the Overview tab.
          </p>
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
