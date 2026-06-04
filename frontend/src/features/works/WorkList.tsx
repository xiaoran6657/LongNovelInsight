import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listWorks, createWork, deleteWork, updateWork } from "../../api/works";
import type { WorkItem } from "../../api/types";
import WorkCard from "./WorkCard";
import WorkUploadPanel from "./WorkUploadPanel";
import WorkAnalysisPanel from "./WorkAnalysisPanel";
import WorkDetail from "./WorkDetail";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";

interface Props {
  topicId: string;
  activeWorkId: string | null;
  onSelectWork: (id: string | null) => void;
}

export default function WorkList({ topicId, activeWorkId, onSelectWork }: Props) {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newIndex, setNewIndex] = useState("");
  const [newAuthor, setNewAuthor] = useState("");
  const [newSubtitle, setNewSubtitle] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const worksQuery = useQuery({
    queryKey: ["works", topicId],
    queryFn: () => listWorks(topicId),
  });

  const createMut = useMutation({
    mutationFn: () =>
      createWork(topicId, {
        title: newTitle,
        subtitle: newSubtitle || null,
        series_index: newIndex ? Number(newIndex) : null,
        author: newAuthor || null,
        description: newDesc || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works", topicId] });
      setShowCreate(false);
      setNewTitle(""); setNewIndex(""); setNewAuthor("");
      setNewSubtitle(""); setNewDesc("");
    },
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editAuthor, setEditAuthor] = useState("");
  const [editIndex, setEditIndex] = useState("");
  const [editSubtitle, setEditSubtitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editError, setEditError] = useState("");
  const [deleteError, setDeleteError] = useState("");

  const deleteMut = useMutation({
    mutationFn: (workId: string) => deleteWork(workId),
    onSuccess: (_data, workId) => {
      setDeleteError("");
      if (workId === activeWorkId) onSelectWork(null);
      queryClient.invalidateQueries({ queryKey: ["works", topicId] });
    },
    onError: (e: Error) => setDeleteError(e.message),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      updateWork(id, body),
    onSuccess: () => {
      setEditError("");
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["works", topicId] });
    },
    onError: (e: Error) => setEditError(e.message),
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
          <input
            type="text"
            placeholder="Subtitle (optional)"
            value={newSubtitle}
            onChange={(e) => setNewSubtitle(e.target.value)}
            style={{ width: "100%", marginBottom: "0.3rem" }}
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            style={{ width: "100%", marginBottom: "0.3rem" }}
          />
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
        <div key={w.id}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <div style={{ flex: 1 }}>
              <WorkCard
                work={w}
                isActive={w.id === activeWorkId}
                onSelect={onSelectWork}
              />
            </div>
            <button
              onClick={() => {
                if (editingId === w.id) {
                  setEditingId(null);
                } else {
                  setEditingId(w.id);
                  setEditError("");
                  setEditTitle(w.title);
                  setEditAuthor(w.author || "");
                  setEditIndex(w.series_index != null ? String(w.series_index) : "");
                  setEditSubtitle(w.subtitle || "");
                  setEditDesc(w.description || "");
                }
              }}
              style={{ fontSize: "0.68rem", padding: "0.15em 0.4em" }}
            >
              {editingId === w.id ? "Cancel" : "Edit"}
            </button>
            <button
              onClick={() => {
                setDeleteError("");
                if (confirm(`Delete "${w.title}"?`)) deleteMut.mutate(w.id);
              }}
              style={{ fontSize: "0.68rem", padding: "0.15em 0.4em", color: "#c62828" }}
              disabled={deleteMut.isPending}
            >
              ×
            </button>
          </div>

          {/* Edit form */}
          {editingId === w.id && (
            <div className="card" style={{ margin: "0.3rem 0 0.5rem 0", background: "#f9fbe7" }}>
              <input
                type="text" placeholder="Title" value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                style={{ width: "100%", marginBottom: "0.3rem", fontSize: "0.8rem" }}
              />
              <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.3rem" }}>
                <input
                  type="number" placeholder="Series #" value={editIndex}
                  onChange={(e) => setEditIndex(e.target.value)}
                  style={{ width: "30%", fontSize: "0.8rem" }}
                />
                <input
                  type="text" placeholder="Author" value={editAuthor}
                  onChange={(e) => setEditAuthor(e.target.value)}
                  style={{ width: "70%", fontSize: "0.8rem" }}
                />
              </div>
              <input type="text" placeholder="Subtitle" value={editSubtitle}
                onChange={(e) => setEditSubtitle(e.target.value)}
                style={{ width: "100%", marginBottom: "0.3rem", fontSize: "0.8rem" }}
              />
              <input type="text" placeholder="Description" value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                style={{ width: "100%", marginBottom: "0.3rem", fontSize: "0.8rem" }}
              />
              <button
                onClick={() =>
                  updateMut.mutate({
                    id: w.id,
                    body: {
                      title: editTitle,
                      author: editAuthor || null,
                      series_index: editIndex ? Number(editIndex) : null,
                      subtitle: editSubtitle || null,
                      description: editDesc || null,
                    },
                  })
                }
                disabled={!editTitle.trim() || updateMut.isPending}
                style={{ fontSize: "0.78rem" }}
              >
                {updateMut.isPending ? "Saving..." : "Save"}
              </button>
              {editError && (
                <p style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.3rem" }}>
                  {editError}
                </p>
              )}
            </div>
          )}
        </div>
      ))}

      {/* Delete error display */}
      {deleteError && (
        <p style={{ color: "#c62828", fontSize: "0.75rem", marginTop: "0.3rem" }}>
          {deleteError}
        </p>
      )}

      {/* Details for selected Work */}
      {activeWorkId && (() => {
        const selected = works.find((w) => w.id === activeWorkId);
        if (!selected) return null;
        const hasDoc = selected.status !== "empty";
        return (
          <div style={{ marginTop: "0.8rem", borderTop: "1px solid #e0e0e0", paddingTop: "0.6rem" }}>
            <WorkDetail work={selected} />
            <WorkUploadPanel workId={activeWorkId} hasDocument={hasDoc} />
            {hasDoc && <WorkAnalysisPanel work={selected} />}
          </div>
        );
      })()}
    </div>
  );
}
