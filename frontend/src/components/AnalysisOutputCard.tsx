import type { AnalysisOutput } from "../api/types";
import { CharactersBlock, RelationsBlock } from "../features/analysis/output/AnalysisEntityBlocks";
import { ChunkTags, EvidenceBlock } from "../features/analysis/output/AnalysisOutputPrimitives";
import { CausalityBlock, EventsBlock } from "../features/analysis/output/AnalysisStoryBlocks";
import { OverviewBlock, ThemesBlock } from "../features/analysis/output/AnalysisSummaryBlocks";
import {
  formatConfidence,
  getString,
  getStringArray,
  inferConfidence,
  normalizeContent,
} from "../features/analysis/output/analysisOutputData";

function FallbackBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  return (
    <div style={{ fontSize: "0.84rem" }}>
      <details>
        <summary style={{ cursor: "pointer", color: "#888" }}>Raw JSON</summary>
        <pre
          style={{
            marginTop: "0.3rem",
            background: "#f5f5f5",
            padding: "0.5rem",
            borderRadius: 3,
            fontSize: "0.75rem",
            overflow: "auto",
            maxHeight: 300,
          }}
        >
          {JSON.stringify(json, null, 2)}
        </pre>
      </details>
      <EvidenceBlock quotes={evidence} />
      <ChunkTags ids={chunks} />
    </div>
  );
}

function MalformedContentBlock() {
  return (
    <div style={{ fontSize: "0.82rem" }}>
      <p style={{ color: "#e65100" }} role="alert">
        This result returned malformed structured content and cannot be displayed safely.
      </p>
    </div>
  );
}

type AnalysisOutputCardProps = {
  output: AnalysisOutput;
  showHiddenNote?: boolean;
};

export default function AnalysisOutputCard({ output }: AnalysisOutputCardProps) {
  const rawJson: unknown = output.content_json;
  const { json, malformed: contentMalformed } = normalizeContent(rawJson);
  const outputConfidence = typeof output.confidence === "number" ? output.confidence : 0;
  const confidence = formatConfidence(inferConfidence(outputConfidence, json));
  const evidence = getStringArray(output.evidence_quotes);
  const chunks = getStringArray(output.source_chunk_ids);
  const outputType = getString(output.output_type, "unknown");
  const title = getString(output.title, `${outputType} output`);

  function renderBody() {
    if (contentMalformed) return <MalformedContentBlock />;
    switch (outputType) {
      case "overview":
        return <OverviewBlock json={json} evidence={evidence} chunks={chunks} />;
      case "characters":
        return <CharactersBlock json={json} evidence={evidence} chunks={chunks} />;
      case "relations":
        return <RelationsBlock json={json} evidence={evidence} chunks={chunks} />;
      case "events":
        return <EventsBlock json={json} evidence={evidence} chunks={chunks} />;
      case "causality":
        return <CausalityBlock json={json} evidence={evidence} chunks={chunks} />;
      case "themes":
        return <ThemesBlock json={json} evidence={evidence} chunks={chunks} />;
      default:
        return <FallbackBlock json={json} evidence={evidence} chunks={chunks} />;
    }
  }

  return (
    <div
      style={{
        background: "#fafafa",
        border: "1px solid #e0e0e0",
        borderRadius: 6,
        padding: "0.75rem 1rem",
        marginBottom: "0.75rem",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.5rem",
        }}
      >
        <p>
          <strong>{title}</strong>
        </p>
        <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
          <span className={`status-badge status-${outputType}`}>{outputType}</span>
          <span style={{ fontSize: "0.78rem", color: confidence.color }}>
            {confidence.text}
            {confidence.text !== "unknown" && " conf."}
          </span>
        </div>
      </div>

      {renderBody()}
    </div>
  );
}
