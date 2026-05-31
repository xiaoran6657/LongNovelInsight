import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { uploadDocument, deleteCurrentDocument, getDocumentMetadata } from "../../api/documents";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";
import DocumentMetadataCard from "../document/DocumentMetadataCard";
import type { Document, DocumentMetadata } from "../../api/types";

interface Props {
  topicId: string;
  document: Document | null | undefined;
  docLoading: boolean;
  docError: Error | null;
}

function parseMetadataJson(metadataJson: string | null | undefined): Record<string, unknown> {
  if (!metadataJson) return {};
  try {
    const parsed = JSON.parse(metadataJson);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // ignore parse errors
  }
  return {};
}

export default function DocumentPanel({ topicId, document, docLoading, docError }: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadDocument(topicId, file),
    onSuccess: () => {
      setUploadError("");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["document", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      queryClient.removeQueries({ queryKey: ["document-metadata", topicId] });
    },
    onError: (e: Error) => setUploadError(e.message),
  });

  const deleteDocMut = useMutation({
    mutationFn: () => deleteCurrentDocument(topicId),
    onSuccess: () => {
      setDeleteError("");
      queryClient.invalidateQueries({ queryKey: ["document", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.removeQueries({ queryKey: ["document-metadata", topicId] });
    },
    onError: (e: Error) => setDeleteError(e.message),
  });

  const hasDoc = document != null;

  const {
    data: metadata,
    isLoading: metaLoading,
    isError: metaError,
  } = useQuery({
    queryKey: ["document-metadata", topicId, document?.id ?? ""],
    queryFn: () => getDocumentMetadata(topicId),
    enabled: hasDoc,
    retry: false,
  });

  // Only trust the metadata endpoint response if it has essential fields.
  // An empty object from a catch-all mock or old backend is not usable.
  const metadataValid =
    metadata != null &&
    typeof (metadata as unknown as Record<string, unknown>).file_type === "string";

  // Fallback metadata built from document object when the metadata endpoint
  // fails, returns incomplete data, or hasn't been called yet.
  const fallbackMeta: DocumentMetadata | null =
    hasDoc && (!metadataValid || metaError)
      ? {
          id: document.id,
          topic_id: document.topic_id,
          original_filename: document.original_filename,
          file_type: document.file_type,
          encoding: document.encoding,
          file_size_bytes: document.file_size_bytes,
          char_count: document.char_count,
          status: document.status,
          metadata: parseMetadataJson(document.metadata_json),
          created_at: document.created_at,
          updated_at: document.updated_at,
        }
      : null;

  const effectiveMetadata: DocumentMetadata | null = metadataValid ? (metadata as DocumentMetadata) : fallbackMeta;

  const fileTypeBadge = (ft: "txt" | "epub") => (
    <span
      style={{
        display: "inline-block",
        padding: "0.15rem 0.5rem",
        borderRadius: 4,
        fontSize: "0.75rem",
        fontWeight: 600,
        background: ft === "epub" ? "#e8f5e9" : "#f5f5f5",
        color: ft === "epub" ? "#2e7d32" : "#616161",
        border: `1px solid ${ft === "epub" ? "#a5d6a7" : "#e0e0e0"}`,
        marginLeft: "0.5rem",
      }}
    >
      {ft.toUpperCase()}
    </span>
  );

  if (docLoading) return <LoadingBlock text="Loading document..." />;

  const is404 = docError != null && String(docError.message).includes("404");
  if (docError && !is404) return <ErrorBlock message={docError.message} />;

  return (
    <div className="card">
      <h3>Document</h3>
      {document ? (
        <div>
          <p>
            <strong>File:</strong> {document.original_filename}
            {fileTypeBadge(document.file_type)}
          </p>
          <p><strong>Size:</strong> {(document.file_size_bytes / 1024).toFixed(1)} KB · {document.char_count.toLocaleString()} chars</p>
          <p><strong>Status:</strong> {document.status}</p>
          <button
            onClick={() => { if (confirm("Delete document and all derived data?")) deleteDocMut.mutate(); }}
            disabled={deleteDocMut.isPending}
            style={{ marginTop: "0.5rem", background: "#e74c3c" }}
          >
            {deleteDocMut.isPending ? "Deleting..." : "Delete Document"}
          </button>
          {deleteError && <p className="field-error" style={{ marginTop: "0.35rem" }}>{deleteError}</p>}

          <DocumentMetadataCard
            metadata={effectiveMetadata}
            isLoading={metaLoading}
          />
        </div>
      ) : (
        <div>
          <p className="text-dim" style={{ fontSize: "0.82rem", marginBottom: "0.5rem" }}>
            Supports TXT (UTF-8/GBK/GB2312/UTF-16) and EPUB files.
            EPUB: text extraction only. DRM-protected files, PDF, and OCR are not supported.
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.epub"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
          <button
            onClick={() => selectedFile && uploadMut.mutate(selectedFile)}
            disabled={!selectedFile || uploadMut.isPending}
            style={{ marginLeft: "0.5rem" }}
          >
            {uploadMut.isPending ? "Uploading..." : "Upload"}
          </button>
          {uploadError && <p className="field-error">{uploadError}</p>}
        </div>
      )}
    </div>
  );
}
