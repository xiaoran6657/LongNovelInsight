import type { AnalysisOutputBlockProps } from "./analysisOutputData";
import {
  getRecordArray,
  getString,
  getStringArray,
  hasAnyEvidence,
} from "./analysisOutputData";
import { ChunkTags, EvidenceBlock, ItemConfBadge } from "./AnalysisOutputPrimitives";

export function OverviewBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const summary =
    getString(json.summary) !== "—"
      ? json.summary
      : getString(json.synopsis) !== "—"
        ? json.synopsis
        : getString(json.overview);

  return (
    <div style={{ fontSize: "0.85rem", lineHeight: 1.5 }}>
      {summary !== "—" && <p style={{ marginBottom: "0.5rem" }}>{String(summary)}</p>}
      {json.main_conflicts != null && (
        <p style={{ marginBottom: "0.3rem" }}>
          <strong>Main conflicts:</strong>{" "}
          {typeof json.main_conflicts === "string"
            ? json.main_conflicts
            : JSON.stringify(json.main_conflicts)}
        </p>
      )}
      {json.narrative_arc != null && (
        <p style={{ marginBottom: "0.3rem" }}>
          <strong>Narrative arc:</strong>{" "}
          {typeof json.narrative_arc === "string"
            ? json.narrative_arc
            : JSON.stringify(json.narrative_arc)}
        </p>
      )}
      {json.world_setting != null && (
        <p style={{ marginBottom: "0.3rem" }}>
          <strong>World setting:</strong>{" "}
          {typeof json.world_setting === "string"
            ? json.world_setting
            : JSON.stringify(json.world_setting)}
        </p>
      )}
      {json.insufficient_evidence != null && (
        <p style={{ color: "#f57f17", fontSize: "0.82rem", fontStyle: "italic" }}>
          Insufficient evidence warning present
        </p>
      )}
      <EvidenceBlock quotes={evidence} />
      <ChunkTags ids={chunks} />
    </div>
  );
}

export function ThemesBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const themes = getRecordArray(json.themes);
  if (themes.length === 0) {
    return <p className="text-dim">No themes found.</p>;
  }
  return (
    <div>
      {themes.map((theme, index) => {
        const name =
          getString(theme.theme) !== "—"
            ? theme.theme
            : getString(theme.name) !== "—"
              ? theme.name
              : `Theme ${index + 1}`;
        const themeKey = `theme-${String(name)}-${index}`;
        return (
          <div
            key={themeKey}
            style={{
              background: "#fff",
              border: "1px solid #eee",
              borderRadius: 4,
              padding: "0.5rem 0.7rem",
              marginBottom: "0.4rem",
              fontSize: "0.84rem",
            }}
          >
            <p style={{ marginBottom: "0.2rem" }}>
              <strong>{String(name)}</strong>
              <ItemConfBadge
                c={typeof theme.confidence === "number" ? theme.confidence : undefined}
              />
            </p>
            {theme.description != null && getString(theme.description) !== "—" && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                {String(theme.description).length > 200
                  ? String(theme.description).slice(0, 200) + "..."
                  : String(theme.description)}
              </p>
            )}
            {theme.development != null && getString(theme.development) !== "—" && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                <span style={{ color: "#888" }}>Development:</span>{" "}
                {String(theme.development).length > 200
                  ? String(theme.development).slice(0, 200) + "..."
                  : String(theme.development)}
              </p>
            )}
            {theme.importance != null && (
              <p style={{ fontSize: "0.78rem", color: "#888" }}>
                Importance: {String(theme.importance)}
              </p>
            )}
            <EvidenceBlock quotes={getStringArray(theme.evidence_quotes)} />
            <ChunkTags ids={getStringArray(theme.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(themes) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}
