import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadToWork } from "../../api/works";
import LoadingBlock from "../../components/LoadingBlock";

interface Props {
  workId: string;
  hasDocument: boolean;
}

export default function WorkUploadPanel({ workId, hasDocument }: Props) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState("");

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadToWork(workId, file),
    onSuccess: () => {
      setUploadError("");
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
    onError: (e: Error) => setUploadError(e.message),
  });

  return (
    <div style={{ marginBottom: "0.5rem" }}>
      <h4 style={{ margin: "0 0 0.3rem 0" }}>Document</h4>
      {hasDocument ? (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          Document already uploaded. Details shown above.
        </p>
      ) : (
        <div>
          <input type="file" accept=".txt,.epub" ref={fileRef} style={{ fontSize: "0.8rem" }} />
          <button
            onClick={() => {
              const f = fileRef.current?.files?.[0];
              if (f) {
                setUploadError("");
                uploadMut.mutate(f);
              }
            }}
            disabled={uploadMut.isPending}
            style={{ fontSize: "0.78rem", marginLeft: "0.4rem" }}
          >
            {uploadMut.isPending ? "Uploading..." : "Upload"}
          </button>
          <p className="text-dim" style={{ fontSize: "0.7rem", marginTop: "0.2rem" }}>
            Accepts .txt and .epub files.
          </p>
          {uploadMut.isPending && <LoadingBlock text="Uploading file..." />}
          {uploadError && (
            <p style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.2rem" }}>{uploadError}</p>
          )}
        </div>
      )}
    </div>
  );
}
