import type { AnalysisOutputBlockProps } from "./analysisOutputData";
import {
  getRecordArray,
  getString,
  getStringArray,
  hasAnyEvidence,
} from "./analysisOutputData";
import { ChunkTags, EvidenceBlock, ItemConfBadge } from "./AnalysisOutputPrimitives";

export function EventsBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const events = getRecordArray(json.events);
  if (events.length === 0) {
    return <p className="text-dim">No events found.</p>;
  }
  return (
    <div>
      {events.map((event, index) => {
        const title =
          getString(event.title) !== "—"
            ? event.title
            : getString(event.event_name) !== "—"
              ? event.event_name
              : getString(event.summary) !== "—"
                ? event.summary
                : `Event ${index + 1}`;
        const eventKey =
          getString(event.event_id_hint) !== "—"
            ? `evt-${String(event.event_id_hint)}`
            : `evt-${index}`;
        return (
          <div
            key={eventKey}
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
              <ItemConfBadge c={typeof event.confidence === "number" ? event.confidence : undefined} />
            </p>
            <p style={{ fontSize: "0.78rem", color: "#888", marginBottom: "0.15rem" }}>
              {event.chapter_index != null && (
                <span style={{ marginRight: "0.75rem" }}>
                  Ch. {String(event.chapter_index)}
                </span>
              )}
              {event.time_order != null && (
                <span style={{ marginRight: "0.75rem" }}>
                  Order: {String(event.time_order)}
                </span>
              )}
              {event.event_id != null && (
                <span style={{ fontFamily: "monospace" }}>{String(event.event_id)}</span>
              )}
            </p>
            {event.description != null && getString(event.description) !== "—" && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                {String(event.description).length > 200
                  ? String(event.description).slice(0, 200) + "..."
                  : String(event.description)}
              </p>
            )}
            {event.participants != null && getStringArray(event.participants).length > 0 && (
              <div
                style={{
                  display: "flex",
                  gap: "0.25rem",
                  flexWrap: "wrap",
                  marginBottom: "0.15rem",
                }}
              >
                {getStringArray(event.participants).map((participant, participantIndex) => (
                  <span
                    key={participantIndex}
                    style={{
                      background: "#e3f2fd",
                      color: "#1565c0",
                      padding: "0.05em 0.4em",
                      borderRadius: 3,
                      fontSize: "0.75rem",
                    }}
                  >
                    {String(participant)}
                  </span>
                ))}
              </div>
            )}
            <EvidenceBlock quotes={getStringArray(event.evidence_quotes)} />
            <ChunkTags ids={getStringArray(event.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(events) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

export function CausalityBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const chains = getRecordArray(json.causal_chains);
  if (chains.length === 0) {
    return <p className="text-dim">No causal chains found.</p>;
  }
  return (
    <div>
      {chains.map((chain, index) => {
        const cause =
          getString(chain.cause) !== "—" ? chain.cause : getString(chain.cause_event_id);
        const effect =
          getString(chain.effect) !== "—" ? chain.effect : getString(chain.effect_event_id);
        const description =
          getString(chain.causal_description) !== "—"
            ? chain.causal_description
            : getString(chain.description);
        const strength =
          getString(chain.causal_strength) !== "—"
            ? chain.causal_strength
            : getString(chain.strength);
        const causalKey = `${String(cause)}-${String(effect)}-${index}`;
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
              {description !== "—" ? (
                <span>
                  {String(description).length > 300
                    ? String(description).slice(0, 300) + "..."
                    : String(description)}
                </span>
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
                <span style={{ marginRight: "0.5rem" }}>Strength: {String(strength)}</span>
              )}
              <ItemConfBadge
                c={typeof chain.confidence === "number" ? chain.confidence : undefined}
              />
              {(getString(chain.cause_event_id) !== "—" ||
                getString(chain.effect_event_id) !== "—") && (
                <span
                  style={{ marginLeft: "0.5rem", fontFamily: "monospace", fontSize: "0.72rem" }}
                >
                  {String(cause)} → {String(effect)}
                </span>
              )}
            </p>
            <EvidenceBlock quotes={getStringArray(chain.evidence_quotes)} />
            <ChunkTags ids={getStringArray(chain.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(chains) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}
