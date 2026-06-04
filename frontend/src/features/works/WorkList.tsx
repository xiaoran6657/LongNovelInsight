import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listWorks, createWork, deleteWork } from "../../api/works";
import type { WorkItem } from "../../api/types";
import WorkCard from "./WorkCard";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";

interface Props {
  topicId: string;
  activeWorkId: string | null;
  onSelectWork: (id: string) => void;
}

export default function WorkList({ topicId, activeWorkId, onSelectWork }: Props) {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newIndex, setNewIndex] = useState("");
  const [newAuthor, setNewAuthor] = useState("");

  const worksQuery = useQuery({
    queryKey: ["works", topicId],
    queryFn: () => listWorks(topicId),
  });

  const createMut = useMutation({
    mutationFn: () =>
      createWork(topicId, {
        title: newTitle,
        series_index: newIndex ? Number(newIndex) : null,
        author: newAuthor || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works", topicId] });
      setShowCreate(false);
      setNewTitle("");
      setNewIndex("");
      setNewAuthor("");
    },
  });

  const deleteMut = useMutation({
    mutationFn: (workId: string) => deleteWork(workId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works", topicId] });
    },
  });

  if (worksQuery.isLoading) return <LoadingBlock text="Loading works..." />;
  if (worksQuery.isError) return <ErrorBlock message="Failed to load works" />;

  const works: WorkItem[] = worksQuery.data?.works ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <h3 style={{ margin: 0 }}>Works</h3>
        <button
          onClick={() => setShowCreate(!showCreate)}
          style={{ fontSize: "0.8rem", padding: "0.2em 0.6em" }}
        >
          {showCreate ? "Cancel" : "+ New Work"}
        </button>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: "0.5rem", background: "#f9fbe7" }}>
          <input
            type="text"
            placeholder="Title (required)"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            style={{ width: "100%", marginBottom: "0.3rem" }}
          />
          <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.3rem" }}>
            <input
              type="number"
              placeholder="Series #"
              value={newIndex}
              onChange={(e) => setNewIndex(e.target.value)}
              style={{ width: "30%" }}
            />
            <input
              type="text"
              placeholder="Author"
              value={newAuthor}
              onChange={(e) => setNewAuthor(e.target.value)}
              style={{ width: "70%" }}
            />
          </div>
          <button
            onClick={() => createMut.mutate()}
            disabled={!newTitle.trim() || createMut.isPending}
            style={{ fontSize: "0.8rem" }}
          >
            {createMut.isPending ? "Creating..." : "Create Work"}
          </button>
          {createMut.isError && (
            <p className="text-dim" style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.3rem" }}>
              {(createMut.error as Error)?.message || "Create failed"}
            </p>
          )}
        </div>
      )}

      {works.length === 0 && (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          Create a Work to add a novel/volume to this Topic. Existing v0.3 Topics are
          automatically represented as one default Work.
        </p>
      )}

      {works.map((w) => (
        <div key={w.id} style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
          <div style={{ flex: 1 }}>
            <WorkCard
              work={w}
              isActive={w.id === activeWorkId}
              onSelect={onSelectWork}
            />
          </div>
          {w.status === "empty" && (
            <button
              onClick={() => {
                if (confirm(`Delete "${w.title}"?`)) deleteMut.mutate(w.id);
              }}
              style={{ fontSize: "0.68rem", padding: "0.15em 0.4em", color: "#c62828" }}
              disabled={deleteMut.isPending}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
