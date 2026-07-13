import type { AnalysisOutputBlockProps } from "./analysisOutputData";
import {
  getRecordArray,
  getString,
  getStringArray,
  hasAnyEvidence,
} from "./analysisOutputData";
import { ChunkTags, EvidenceBlock, ItemConfBadge } from "./AnalysisOutputPrimitives";

export function CharactersBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const characters = getRecordArray(json.characters);
  if (characters.length === 0) {
    return <p className="text-dim">No characters found.</p>;
  }
  return (
    <div>
      {characters.map((character, index) => {
        const characterKey =
          getString(character.character_id_hint) !== "—"
            ? String(character.character_id_hint)
            : getString(character.name) !== "—"
              ? String(character.name)
              : `char-${index}`;
        return (
          <div
            key={characterKey}
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
              <strong>{getString(character.name, `Character ${index + 1}`)}</strong>
              {character.role != null && (
                <span style={{ color: "#666", marginLeft: "0.4rem" }}>
                  {String(character.role)}
                </span>
              )}
              <ItemConfBadge
                c={typeof character.confidence === "number" ? character.confidence : undefined}
              />
            </p>
            {character.traits != null && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                <span style={{ color: "#888" }}>Traits:</span>{" "}
                {Array.isArray(character.traits)
                  ? character.traits.join(", ")
                  : String(character.traits)}
              </p>
            )}
            {character.aliases != null && getStringArray(character.aliases).length > 0 && (
              <p style={{ fontSize: "0.78rem", marginBottom: "0.15rem" }}>
                <span style={{ color: "#888" }}>Aliases:</span>{" "}
                {getStringArray(character.aliases).join(", ")}
              </p>
            )}
            {character.description != null && getString(character.description) !== "—" && (
              <p style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                {String(character.description).length > 200
                  ? String(character.description).slice(0, 200) + "..."
                  : String(character.description)}
              </p>
            )}
            {character.first_appearance_chapter != null && (
              <p style={{ fontSize: "0.78rem", color: "#888" }}>
                First appears: chapter {String(character.first_appearance_chapter)}
              </p>
            )}
            <EvidenceBlock quotes={getStringArray(character.evidence_quotes)} />
            <ChunkTags ids={getStringArray(character.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(characters) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}

export function RelationsBlock({ json, evidence, chunks }: AnalysisOutputBlockProps) {
  const relationships = getRecordArray(json.relationships);
  if (relationships.length === 0) {
    return <p className="text-dim">No relationships found.</p>;
  }
  return (
    <div>
      {relationships.map((relationship, index) => {
        const source =
          getString(relationship.source_character) !== "—"
            ? relationship.source_character
            : getString(relationship.character_a);
        const target =
          getString(relationship.target_character) !== "—"
            ? relationship.target_character
            : getString(relationship.character_b);
        const relationType =
          getString(relationship.relation_type) !== "—"
            ? relationship.relation_type
            : getString(relationship.relationship);
        const relationshipKey = `${String(source)}-${String(target)}-${index}`;
        return (
          <div
            key={relationshipKey}
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
              {relationType !== "—" && (
                <span style={{ color: "#666", marginLeft: "0.4rem" }}>
                  ({String(relationType)})
                </span>
              )}
              <ItemConfBadge
                c={
                  typeof relationship.confidence === "number"
                    ? relationship.confidence
                    : undefined
                }
              />
            </p>
            {relationship.description != null && getString(relationship.description) !== "—" && (
              <p style={{ fontSize: "0.8rem" }}>
                {String(relationship.description).length > 200
                  ? String(relationship.description).slice(0, 200) + "..."
                  : String(relationship.description)}
              </p>
            )}
            <EvidenceBlock quotes={getStringArray(relationship.evidence_quotes)} />
            <ChunkTags ids={getStringArray(relationship.source_chunk_ids)} />
          </div>
        );
      })}
      {!hasAnyEvidence(relationships) && <EvidenceBlock quotes={evidence} />}
      <ChunkTags ids={chunks} />
    </div>
  );
}
