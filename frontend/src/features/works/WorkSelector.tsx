import { useQuery } from "@tanstack/react-query";
import { listWorks } from "../../api/works";
import type { WorkItem } from "../../api/types";

interface Props {
  topicId: string;
  activeWorkId: string | null;
  onSelectWork: (id: string | null) => void;
}

export default function WorkSelector({ topicId, activeWorkId, onSelectWork }: Props) {
  const worksQuery = useQuery({
    queryKey: ["works", topicId],
    queryFn: () => listWorks(topicId),
    enabled: !!topicId,
  });

  const works: WorkItem[] = worksQuery.data?.works ?? [];

  if (!worksQuery.data || works.length <= 1) return null;

  return (
    <div style={{
      display: "flex", gap: "0.3rem", alignItems: "center",
      marginBottom: "0.5rem", padding: "0.3rem 0.5rem",
      background: "#f5f5f5", borderRadius: 4, flexWrap: "wrap",
    }}>
      <span className="text-dim" style={{ fontSize: "0.75rem", fontWeight: 600 }}>Work:</span>
      <button
        onClick={() => onSelectWork(null)}
        style={{
          fontSize: "0.74rem",
          padding: "0.15em 0.5em",
          background: activeWorkId === null ? "#1976d2" : "#fff",
          color: activeWorkId === null ? "#fff" : "#333",
          border: activeWorkId === null ? "1px solid #1976d2" : "1px solid #ccc",
          borderRadius: 3,
          cursor: "pointer",
        }}
      >
        All
      </button>
      {works.map((w) => {
        const active = w.id === activeWorkId;
        return (
          <button
            key={w.id}
            onClick={() => onSelectWork(w.id)}
            style={{
              fontSize: "0.74rem",
              padding: "0.15em 0.5em",
              background: active ? "#1976d2" : "#fff",
              color: active ? "#fff" : "#333",
              border: active ? "1px solid #1976d2" : "1px solid #ccc",
              borderRadius: 3,
              cursor: "pointer",
            }}
          >
            {w.series_index != null && `${w.series_index}. `}{w.title}
          </button>
        );
      })}
    </div>
  );
}
