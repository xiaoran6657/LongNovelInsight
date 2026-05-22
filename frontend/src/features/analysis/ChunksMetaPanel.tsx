import { useQuery } from "@tanstack/react-query";
import { getChunksMeta } from "../../api/parse";
import type { ChunksMetaResponse } from "../../api/types";
import { ApiError } from "../../api/client";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";

function fmt(n: number): string {
  return n.toLocaleString();
}

interface Props {
  topicId: string;
  hasDoc: boolean;
}

function MetaDisplay({ data }: { data: ChunksMetaResponse }) {
  return (
    <div className="card" style={{ fontSize: "0.85rem" }}>
      <h3>Chunks Meta</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem" }}>
        <div><strong>Chunks:</strong> {data.chunk_count}</div>
        <div><strong>Chapters:</strong> {data.chapter_count}</div>
        <div><strong>Total chars:</strong> {fmt(data.total_chars)}</div>
        <div><strong>Est. tokens:</strong> {fmt(data.estimated_tokens)}</div>
        {data.first_chunk_index != null && <div><strong>First chunk:</strong> {data.first_chunk_index}</div>}
        {data.last_chunk_index != null && <div><strong>Last chunk:</strong> {data.last_chunk_index}</div>}
      </div>
      {data.chunks_by_chapter.length > 0 && (
        <details style={{ marginTop: "0.5rem" }}>
          <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: "0.82rem" }}>
            Per-chapter breakdown ({data.chunks_by_chapter.length} chapters)
          </summary>
          <div style={{ maxHeight: 200, overflowY: "auto", marginTop: "0.25rem" }}>
            {data.chunks_by_chapter.map((ch) => (
              <div key={ch.chapter_index} style={{ padding: "0.2rem 0", borderBottom: "1px solid #eee", fontSize: "0.78rem" }}>
                <strong>Ch. {ch.chapter_index + 1}</strong> — {ch.title}{" "}
                <span className="text-dim">
                  ({ch.chunk_count} chunks, {fmt(ch.char_count)} chars, ~{fmt(ch.estimated_tokens)} tokens)
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export default function ChunksMetaPanel({ topicId, hasDoc }: Props) {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["chunks-meta", topicId],
    queryFn: () => getChunksMeta(topicId),
    enabled: !!topicId && hasDoc,
  });

  if (!hasDoc) {
    return (
      <div className="card">
        <h3>Chunks Meta</h3>
        <p className="text-dim">Upload and parse a document first.</p>
      </div>
    );
  }

  if (isLoading) return <LoadingBlock text="Loading chunks meta..." />;
  if (isError || !data) {
    const apiErr = error instanceof ApiError ? error : undefined;
    return (
      <div className="card">
        <h3>Chunks Meta</h3>
        <ErrorBlock
          title="Failed to load chunk metadata"
          message={apiErr?.detail ?? (isError ? "Backend v2 /chunks/meta not available. Parse the document to see chunk counts." : "No chunk data yet.")}
          status={apiErr?.status}
          detail={apiErr?.detail ? `HTTP ${apiErr.status}: ${apiErr.detail}` : undefined}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return <MetaDisplay data={data} />;
}
