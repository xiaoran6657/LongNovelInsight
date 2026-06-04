import { useQuery } from "@tanstack/react-query";
import { getWorkDocument, listWorkChapters, listWorkChunks } from "../../api/works";
import type { WorkItem } from "../../api/types";
import LoadingBlock from "../../components/LoadingBlock";

interface Props {
  work: WorkItem;
}

export default function WorkDetail({ work }: Props) {
  const docQuery = useQuery({
    queryKey: ["work-document", work.id],
    queryFn: () => getWorkDocument(work.id),
    enabled: work.status !== "empty",
  });

  const chaptersQuery = useQuery({
    queryKey: ["work-chapters", work.id],
    queryFn: () => listWorkChapters(work.id),
    enabled: work.status === "parsed" || work.status === "analyzed",
  });

  const chunksQuery = useQuery({
    queryKey: ["work-chunks", work.id],
    queryFn: () => listWorkChunks(work.id),
    enabled: work.status === "parsed" || work.status === "analyzed",
  });

  if (work.status === "empty") {
    return (
      <p className="text-dim" style={{ fontSize: "0.8rem" }}>
        No document uploaded yet.
      </p>
    );
  }

  return (
    <div style={{ marginTop: "0.6rem", fontSize: "0.82rem" }}>
      {docQuery.isLoading && <LoadingBlock text="Loading document..." />}

      {docQuery.data && (
        <div>
          <p><strong>File:</strong> {docQuery.data.original_filename} ({docQuery.data.file_type})</p>
          <p><strong>Size:</strong> {(docQuery.data.file_size_bytes / 1024).toFixed(1)} KB ·{" "}
            <strong>Chars:</strong> {docQuery.data.char_count.toLocaleString()}</p>
          <p><strong>Encoding:</strong> {docQuery.data.encoding} ·{" "}
            <strong>Status:</strong> {docQuery.data.status}</p>
        </div>
      )}

      {chaptersQuery.data && (
        <p style={{ marginTop: "0.3rem" }}>
          <strong>Chapters:</strong> {chaptersQuery.data.chapters.length}
        </p>
      )}

      {chunksQuery.data && (
        <p>
          <strong>{chunksQuery.data.chunks.length >= 100 ? "Showing chunks" : "Chunks"}:</strong>{" "}
          {chunksQuery.data.chunks.length}
          {chunksQuery.data.chunks.length >= 100 && " (may not be total)"}
        </p>
      )}

      {chaptersQuery.isError && (
        <p className="text-dim">Could not load chapters.</p>
      )}
    </div>
  );
}
