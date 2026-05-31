import type { DocumentMetadata } from "../../api/types";

interface Props {
  metadata: DocumentMetadata | null;
  isLoading: boolean;
}

function safeString(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((v) => safeString(v) ?? "").filter(Boolean).join(", ") || null;
  return null;
}

function MetadataField({ label, value }: { label: string; value: unknown }) {
  const display = safeString(value);
  if (!display) return null;
  return (
    <div style={{ marginBottom: "0.15rem" }}>
      <span style={{ color: "#888", marginRight: "0.35rem" }}>{label}:</span>
      <span>{display}</span>
    </div>
  );
}

export default function DocumentMetadataCard({ metadata, isLoading }: Props) {
  if (isLoading) return <p className="text-dim">Loading metadata...</p>;
  if (!metadata || typeof metadata.file_type !== "string") return null;

  const isEpub = metadata.file_type === "epub";
  const meta = metadata.metadata ?? {};

  return (
    <div className="card" style={{ marginTop: "0.5rem" }}>
      <h3>Document Metadata</h3>

      <div style={{ marginBottom: "0.5rem" }}>
        <span
          style={{
            display: "inline-block",
            padding: "0.15rem 0.5rem",
            borderRadius: 4,
            fontSize: "0.75rem",
            fontWeight: 600,
            background: isEpub ? "#e8f5e9" : "#f5f5f5",
            color: isEpub ? "#2e7d32" : "#616161",
            border: `1px solid ${isEpub ? "#a5d6a7" : "#e0e0e0"}`,
          }}
        >
          {metadata.file_type.toUpperCase()}
        </span>
      </div>

      {isEpub && (
        <div style={{ fontSize: "0.82rem", lineHeight: 1.6 }}>
          <MetadataField label="Source Format" value={meta.source_format} />
          <MetadataField label="Title" value={meta.title ?? meta["dc:title"]} />
          <MetadataField label="Creator" value={meta.creator ?? meta["dc:creator"]} />
          <MetadataField label="Language" value={meta.language ?? meta["dc:language"]} />
          <MetadataField label="Publisher" value={meta.publisher ?? meta["dc:publisher"]} />
          <MetadataField label="Identifier" value={meta.identifier ?? meta["dc:identifier"]} />

          {Array.isArray(meta.parsing_warnings) &&
            (meta.parsing_warnings as unknown[]).length > 0 && (
              <details style={{ marginTop: "0.5rem" }}>
                <summary
                  style={{
                    cursor: "pointer",
                    color: "#e65100",
                    fontWeight: 600,
                    fontSize: "0.8rem",
                  }}
                >
                  Parsing Warnings ({(meta.parsing_warnings as unknown[]).length})
                </summary>
                <ul
                  style={{
                    marginTop: "0.25rem",
                    paddingLeft: "1.2rem",
                    fontSize: "0.75rem",
                    color: "#bf360c",
                  }}
                >
                  {(meta.parsing_warnings as unknown[]).map((w, i) => (
                    <li key={i}>{safeString(w) ?? String(w)}</li>
                  ))}
                </ul>
              </details>
            )}
        </div>
      )}

      {!isEpub && (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          TXT documents have no embedded metadata.
        </p>
      )}
    </div>
  );
}
