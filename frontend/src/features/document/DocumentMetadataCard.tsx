import type { DocumentMetadata } from "../../api/types";

interface Props {
  metadata: DocumentMetadata | null;
  isLoading: boolean;
}

export default function DocumentMetadataCard({ metadata, isLoading }: Props) {
  if (isLoading) return <p className="text-dim">Loading metadata...</p>;
  if (!metadata) return null;

  const isEpub = metadata.file_type === "epub";
  const meta = metadata.metadata ?? {};

  return (
    <div className="card" style={{ marginTop: "0.5rem" }}>
      <h3>Document Metadata</h3>

      {/* File type badge */}
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
          {renderField("Title", meta.title ?? meta["dc:title"])}
          {renderField("Creator", meta.creator ?? meta["dc:creator"])}
          {renderField("Language", meta.language ?? meta["dc:language"])}
          {renderField("Publisher", meta.publisher ?? meta["dc:publisher"])}

          {/* Parsing warnings */}
          {Array.isArray(meta.parsing_warnings) &&
            (meta.parsing_warnings as string[]).length > 0 && (
              <details style={{ marginTop: "0.5rem" }}>
                <summary
                  style={{
                    cursor: "pointer",
                    color: "#e65100",
                    fontWeight: 600,
                    fontSize: "0.8rem",
                  }}
                >
                  Parsing Warnings ({(meta.parsing_warnings as string[]).length})
                </summary>
                <ul
                  style={{
                    marginTop: "0.25rem",
                    paddingLeft: "1.2rem",
                    fontSize: "0.75rem",
                    color: "#bf360c",
                  }}
                >
                  {(meta.parsing_warnings as string[]).map((w, i) => (
                    <li key={i}>{w}</li>
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

function renderField(label: string, value: unknown) {
  if (!value) return null;
  const display = typeof value === "string" ? value : String(value);
  return (
    <div style={{ marginBottom: "0.15rem" }}>
      <span style={{ color: "#888", marginRight: "0.35rem" }}>{label}:</span>
      <span>{display}</span>
    </div>
  );
}
