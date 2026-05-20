import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parseTopic } from "../../api/parse";
import type { ParseResult } from "../../api/types";

interface Props {
  topicId: string;
  hasDocument: boolean;
}

export default function ParsePanel({ topicId, hasDocument }: Props) {
  const queryClient = useQueryClient();
  const [parseError, setParseError] = useState("");

  const parseMut = useMutation({
    mutationFn: (force?: boolean) => parseTopic(topicId, force ?? false),
    onSuccess: () => {
      setParseError("");
      queryClient.invalidateQueries({ queryKey: ["chapters", topicId] });
      queryClient.invalidateQueries({ queryKey: ["chunks-meta", topicId] });
    },
    onError: (e: Error) => setParseError(e.message),
  });

  const result = parseMut.data as ParseResult | undefined;

  if (!hasDocument) {
    return (
      <div className="card">
        <h3>Parse</h3>
        <p className="text-dim">Upload a document first.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3>Parse</h3>
      <button
        onClick={() => parseMut.mutate(undefined)}
        disabled={parseMut.isPending}
      >
        {parseMut.isPending ? "Parsing..." : result ? "Re-parse" : "Parse Document"}
      </button>
      {parseError && <p className="field-error">{parseError}</p>}
      {result && (
        <div style={{ marginTop: "0.5rem" }}>
          <p>
            <strong>Chapters:</strong> {result.chapter_count} ·{" "}
            <strong>Chunks:</strong> {result.chunk_count} ·{" "}
            <strong>Chars:</strong> {result.char_count?.toLocaleString()} ·{" "}
            <strong>Est. tokens:</strong> {result.estimated_tokens?.toLocaleString()}
          </p>
          {result.already_parsed && (
            <p className="text-dim">Already parsed — re-parse to force refresh.</p>
          )}
        </div>
      )}
    </div>
  );
}
