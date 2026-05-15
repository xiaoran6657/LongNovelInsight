import type { AnalysisOutput } from "../api/types";

function fmtConf(c: number | null | undefined): {
  text: string;
  color: string;
} {
  if (c == null || isNaN(c)) return { text: "unknown", color: "#999" };
  if (c >= 0.7) return { text: `${(c * 100).toFixed(0)}%`, color: "#27ae60" };
  if (c >= 0.4) return { text: `${(c * 100).toFixed(0)}%`, color: "#f57f17" };
  return { text: `${(c * 100).toFixed(0)}%`, color: "#e74c3c" };
}

function collectItemConfidences(json: Record<string, unknown>): number[] {
  const results: number[] = [];
  for (const [, value] of Object.entries(json)) {
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (
        item &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).confidence === "number"
      ) {
        const c = (item as Record<string, unknown>).confidence as number;
        if (!isNaN(c)) results.push(c);
      }
    }
  }
  return results;
}

function inferConfidence(
  outputConfidence: number,
  json: Record<string, unknown> | null
): number | null {
  // Top-level confidence > 0 → use it (e.g. overview has it)
  if (outputConfidence > 0) return outputConfidence;
  // Otherwise extract from item-level confidences
  if (!json) return null;
  const items = collectItemConfidences(json);
  if (items.length === 0) return null;
  return items.reduce((a, b) => a + b, 0) / items.length;
}

function ItemConfBadge({ c }: { c: number | null | undefined }) {
  const { text, color } = fmtConf(c);
  return (
    <span
      style={{
        fontSize: "0.72rem",
        color,
        fontWeight: 600,
        marginLeft: "0.35rem",
      }}
    >
      {text}
    </span>
  );
}

function EvidenceBlock({ quotes }: { quotes: string[] }) {
  if (quotes.length === 0) return null;
  return (
    <div style={{ marginTop: "0.3rem" }}>
      <span
        style={{ fontSize: "0.72rem", fontWeight: 600, color: "#aaa" }}
      >
        Evidence:
      </span>
      {quotes.map((q, i) => (
        <blockquote
          key={i}
          style={{
            margin: "0.1rem 0 0.2rem 0",
            padding: "0.15rem 0.5rem",
            borderLeft: "2px solid #ddd",
            fontSize: "0.78rem",
            color: "#777",
            fontStyle: "italic",
          }}
        >
          {q.length > 250 ? q.slice(0, 250) + "..." : q}
        </blockquote>
      ))}
    </div>
  );
}

function ChunkTags({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: "0.2rem",
        flexWrap: "wrap",
        marginTop: "0.25rem",
      }}
    >
      {ids.map((id) => (
        <span key={id} className="chunk-tag">
          {id.length > 10 ? id.slice(0, 10) + "…" : id}
        </span>
      ))}
    </div>
  );
}

function getString(v: unknown, fallback: string = "—"): string {
  if (typeof v === "string" && v.trim()) return v;
  return fallback;
}

function getArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  return [];
}

function getStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((item) => (typeof item === "string" ? item : String(item ?? "")));
}

function hasAnyEvidence(items: unknown[]): boolean {
  for (const item of items) {
    if (item && typeof item === "object") {
      const ev = (item as Record<string, unknown>).evidence_quotes;
      if (Array.isArray(ev) && ev.length > 0) return true;
    }
  }
  return false;
}

// ── Type-specific renderers ──

function OverviewBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const summary =
    getString(json.summary) !== "—"
      ? json.summary
      : getString(json.synopsis) !== "—"
        ? json.synopsis
        : getString(json.overview);

  return (
    <div style={{ fontSize: "0.85rem", lineHeight: 1.5 }}>
      {summary !== "—" && (
        <p style={{ marginBottom: "0.5rem" }}>{String(summary)}</p>
      )}
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

function CharactersBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const chars = getArray(json.characters);
  if (chars.length === 0) {
    return <p className="text-dim">No characters found.</p>;
  }
  return (
    <div>
      {chars.map((c, i) => {
        const item = c as Record<string, unknown>;
        const cKey =
          getString(item.character_id_hint) !== "—"
            ? String(item.character_id_hint)
            : getString(item.name) !== "—"
              ? String(item.name)
              : `char-${i}`;
        return (
          <div
            key={cKey}
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
              <strong>{getString(item.name, `Character ${i + 1}`)}</strong>
              {item.role != null && (
                <span style={{ color: "#666", marginLeft: "0.4rem" }}>
                  {String(item.role)}
                </span>
              )}
              <ItemConfBadge
                c={
                  typeof item.confidence === "number"
                    ? item.confidence
                    : undefined
                }
              />
            </p>
            {item.traits != null && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                <span style={{ color: "#888" }}>Traits:</span>{" "}
                {Array.isArray(item.traits)
                  ? item.traits.join(", ")
                  : String(item.traits)}
              </p>
            )}
            {item.aliases != null &&
              getStringArray(item.aliases).length > 0 && (
                <p style={{ fontSize: "0.78rem", marginBottom: "0.15rem" }}>
                  <span style={{ color: "#888" }}>Aliases:</span>{" "}
                  {getStringArray(item.aliases).join(", ")}
                </p>
              )}
            {item.description != null &&
              getString(item.description) !== "—" && (
                <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                  {String(item.description).length > 200
                    ? String(item.description).slice(0, 200) + "..."
                    : String(item.description)}
                </p>
              )}
            {item.first_appearance_chapter != null && (
              <p style={{ fontSize: "0.78rem", color: "#888" }}>
                First appears: chapter {String(item.first_appearance_chapter)}
              </p>
            )}
            <EvidenceBlock
              quotes={getStringArray(item.evidence_quotes)}
            />
            <ChunkTags ids={getStringArray(item.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(chars) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

function RelationsBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const rels = getArray(json.relationships);
  if (rels.length === 0) {
    return <p className="text-dim">No relationships found.</p>;
  }
  return (
    <div>
      {rels.map((r, i) => {
        const item = r as Record<string, unknown>;
        const source =
          getString(item.source_character) !== "—"
            ? item.source_character
            : getString(item.character_a);
        const target =
          getString(item.target_character) !== "—"
            ? item.target_character
            : getString(item.character_b);
        const relType =
          getString(item.relation_type) !== "—"
            ? item.relation_type
            : getString(item.relationship);
        const relKey = `${String(source)}-${String(target)}-${i}`;
        return (
          <div
            key={relKey}
            style={{
              background: "#fff",
              border: "1px solid #eee",
              borderRadius: 4,
              padding: "0.5rem 0.7rem",
              marginBottom: "0.4rem",
              fontSize: "0.84rem",
            }}
          >
            <p style={{ marginBottom: "0.15rem" }}>
              <strong>{String(source)}</strong>
              <span style={{ color: "#888", margin: "0 0.3rem" }}>→</span>
              <strong>{String(target)}</strong>
              {relType !== "—" && (
                <span style={{ color: "#666", marginLeft: "0.4rem" }}>
                  ({String(relType)})
                </span>
              )}
              <ItemConfBadge
                c={
                  typeof item.confidence === "number"
                    ? item.confidence
                    : undefined
                }
              />
            </p>
            {item.description != null &&
              getString(item.description) !== "—" && (
                <p style={{ fontSize: "0.8rem" }}>
                  {String(item.description).length > 200
                    ? String(item.description).slice(0, 200) + "..."
                    : String(item.description)}
                </p>
              )}
            <EvidenceBlock
              quotes={getStringArray(item.evidence_quotes)}
            />
            <ChunkTags ids={getStringArray(item.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(rels) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

function EventsBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const evts = getArray(json.events);
  if (evts.length === 0) {
    return <p className="text-dim">No events found.</p>;
  }
  return (
    <div>
      {evts.map((e, i) => {
        const item = e as Record<string, unknown>;
        const title =
          getString(item.title) !== "—"
            ? item.title
            : getString(item.event_name) !== "—"
              ? item.event_name
              : getString(item.summary) !== "—"
                ? item.summary
                : `Event ${i + 1}`;
        const evtKey =
          getString(item.event_id_hint) !== "—"
            ? `evt-${String(item.event_id_hint)}`
            : `evt-${i}`;
        return (
          <div
            key={evtKey}
            style={{
              background: "#fff",
              border: "1px solid #eee",
              borderRadius: 4,
              padding: "0.5rem 0.7rem",
              marginBottom: "0.4rem",
              fontSize: "0.84rem",
            }}
          >
            <p style={{ marginBottom: "0.15rem" }}>
              <strong>{String(title)}</strong>
              <ItemConfBadge
                c={
                  typeof item.confidence === "number"
                    ? item.confidence
                    : undefined
                }
              />
            </p>
            <p style={{ fontSize: "0.78rem", color: "#888", marginBottom: "0.15rem" }}>
              {item.chapter_index != null && (
                <span style={{ marginRight: "0.75rem" }}>
                  Ch. {String(item.chapter_index)}
                </span>
              )}
              {item.time_order != null && (
                <span style={{ marginRight: "0.75rem" }}>
                  Order: {String(item.time_order)}
                </span>
              )}
              {item.event_id != null && (
                <span style={{ fontFamily: "monospace" }}>
                  {String(item.event_id)}
                </span>
              )}
            </p>
            {item.description != null &&
              getString(item.description) !== "—" && (
                <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                  {String(item.description).length > 200
                    ? String(item.description).slice(0, 200) + "..."
                    : String(item.description)}
                </p>
              )}
            {item.participants != null &&
              getStringArray(item.participants).length > 0 && (
                <div
                  style={{
                    display: "flex",
                    gap: "0.25rem",
                    flexWrap: "wrap",
                    marginBottom: "0.15rem",
                  }}
                >
                  {getStringArray(item.participants).map((p, j) => (
                    <span
                      key={j}
                      style={{
                        background: "#e3f2fd",
                        color: "#1565c0",
                        padding: "0.05em 0.4em",
                        borderRadius: 3,
                        fontSize: "0.75rem",
                      }}
                    >
                      {String(p)}
                    </span>
                  ))}
                </div>
              )}
            <EvidenceBlock
              quotes={getStringArray(item.evidence_quotes)}
            />
            <ChunkTags ids={getStringArray(item.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(evts) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

function CausalityBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const chains = getArray(json.causal_chains);
  if (chains.length === 0) {
    return <p className="text-dim">No causal chains found.</p>;
  }
  return (
    <div>
      {chains.map((c, i) => {
        const item = c as Record<string, unknown>;
        const cause =
          getString(item.cause) !== "—"
            ? item.cause
            : getString(item.cause_event_id);
        const effect =
          getString(item.effect) !== "—"
            ? item.effect
            : getString(item.effect_event_id);
        const desc =
          getString(item.causal_description) !== "—"
            ? item.causal_description
            : getString(item.description);
        const strength =
          getString(item.causal_strength) !== "—"
            ? item.causal_strength
            : getString(item.strength);
        const causalKey = `${String(cause)}-${String(effect)}-${i}`;
        return (
          <div
            key={causalKey}
            style={{
              background: "#fff",
              border: "1px solid #eee",
              borderRadius: 4,
              padding: "0.5rem 0.7rem",
              marginBottom: "0.4rem",
              fontSize: "0.84rem",
            }}
          >
            <p style={{ marginBottom: "0.25rem", lineHeight: 1.5 }}>
              {desc !== "—" ? (
                <span>{String(desc).length > 300
                  ? String(desc).slice(0, 300) + "..."
                  : String(desc)}</span>
              ) : (
                <span>
                  <strong>{String(cause)}</strong>
                  <span style={{ color: "#888", margin: "0 0.3rem" }}>→</span>
                  <strong>{String(effect)}</strong>
                </span>
              )}
            </p>
            <p style={{ fontSize: "0.76rem", color: "#888", marginBottom: "0.15rem" }}>
              {strength !== "—" && (
                <span style={{ marginRight: "0.5rem" }}>
                  Strength: {String(strength)}
                </span>
              )}
              <ItemConfBadge
                c={
                  typeof item.confidence === "number"
                    ? item.confidence
                    : undefined
                }
              />
              {(getString(item.cause_event_id) !== "—" ||
                getString(item.effect_event_id) !== "—") && (
                <span style={{ marginLeft: "0.5rem", fontFamily: "monospace", fontSize: "0.72rem" }}>
                  {String(cause)} → {String(effect)}
                </span>
              )}
            </p>
            <EvidenceBlock
              quotes={getStringArray(item.evidence_quotes)}
            />
            <ChunkTags ids={getStringArray(item.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(chains) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

function ThemesBlock({
  json,
  evidence,
  chunks,
}: {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
}) {
  const themes = getArray(json.themes);
  if (themes.length === 0) {
    return <p className="text-dim">No themes found.</p>;
  }
  return (
    <div>
      {themes.map((t, i) => {
        const item = t as Record<string, unknown>;
        const name =
          getString(item.theme) !== "—"
            ? item.theme
            : getString(item.name) !== "—"
              ? item.name
              : `Theme ${i + 1}`;
        const themeKey = `theme-${String(name)}-${i}`;
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
                c={
                  typeof item.confidence === "number"
                    ? item.confidence
                    : undefined
                }
              />
            </p>
            {item.description != null &&
              getString(item.description) !== "—" && (
                <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                  {String(item.description).length > 200
                    ? String(item.description).slice(0, 200) + "..."
                    : String(item.description)}
                </p>
              )}
            {item.development != null &&
              getString(item.development) !== "—" && (
                <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                  <span style={{ color: "#888" }}>Development:</span>{" "}
                  {String(item.development).length > 200
                    ? String(item.development).slice(0, 200) + "..."
                    : String(item.development)}
                </p>
              )}
            {item.importance != null && (
              <p style={{ fontSize: "0.78rem", color: "#888" }}>
                Importance: {String(item.importance)}
              </p>
            )}
            <EvidenceBlock
              quotes={getStringArray(item.evidence_quotes)}
            />
            <ChunkTags ids={getStringArray(item.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(themes) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

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
        <summary style={{ cursor: "pointer", color: "#888" }}>
          Raw JSON
        </summary>
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

// ── Main card component ──

interface AnalysisOutputCardProps {
  output: AnalysisOutput;
  showHiddenNote?: boolean;
}

export default function AnalysisOutputCard({
  output,
}: AnalysisOutputCardProps) {
  const json = output.content_json ?? {};
  const conf = fmtConf(inferConfidence(output.confidence, json));
  const evidence = output.evidence_quotes ?? [];
  const chunks = output.source_chunk_ids ?? [];

  function renderBody() {
    switch (output.output_type) {
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
          <strong>{output.title}</strong>
        </p>
        <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
          <span className={`status-badge status-${output.output_type}`}>
            {output.output_type}
          </span>
          <span style={{ fontSize: "0.78rem", color: conf.color }}>
            {conf.text}
            {conf.text !== "unknown" && " conf."}
          </span>
        </div>
      </div>

      {renderBody()}
    </div>
  );
}
