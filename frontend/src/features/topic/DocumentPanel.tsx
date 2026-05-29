import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { uploadDocument, deleteCurrentDocument, getDocumentMetadata } from "../../api/documents";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";
import DocumentMetadataCard from "../document/DocumentMetadataCard";
import type { DocumentSummary } from "../../api/types";

interface Props {
  topicId: string;
  document: DocumentSummary | null | undefined;
  docLoading: boolean;
  docError: Error | null;
}

export default function DocumentPanel({ topicId, document, docLoading, docError }: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState("");
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
    },
    onError: (e: Error) => setUploadError(e.message),
  });

  const deleteDocMut = useMutation({
    mutationFn: () => deleteCurrentDocument(topicId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
    },
  });

  const hasDoc = document != null;

  const { data: metadata, isLoading: metaLoading } = useQuery({
    queryKey: ["document-metadata", topicId],
    queryFn: () => getDocumentMetadata(topicId),
    enabled: hasDoc && document.status === "parsed",
  });

  if (docLoading) return <LoadingBlock text="Loading document..." />;

  const is404 = docError != null && String(docError.message).includes("404");
  if (docError && !is404) return <ErrorBlock message={docError.message} />;

  return (
    <div className="card">
      <h3>Document</h3>
      {document ? (
        <div>
          <p><strong>File:</strong> {document.original_filename}</p>
          <p><strong>Size:</strong> {(document.file_size_bytes / 1024).toFixed(1)} KB · {document.char_count.toLocaleString()} chars</p>
          <p><strong>Status:</strong> {document.status}</p>
          <button
            onClick={() => { if (confirm("Delete document and all derived data?")) deleteDocMut.mutate(); }}
            disabled={deleteDocMut.isPending}
            style={{ marginTop: "0.5rem", background: "#e74c3c" }}
          >
            {deleteDocMut.isPending ? "Deleting..." : "Delete Document"}
          </button>

          <DocumentMetadataCard
            metadata={metadata ?? null}
            isLoading={metaLoading}
          />
        </div>
      ) : (
        <div>
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
