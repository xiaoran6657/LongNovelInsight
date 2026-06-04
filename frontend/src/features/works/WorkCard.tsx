import type { WorkItem } from "../../api/types";
import StatusBadge from "../../components/StatusBadge";

interface Props {
  work: WorkItem;
  isActive: boolean;
  onSelect: (id: string) => void;
}

const STATUS_TONES: Record<string, "ok" | "warn" | "info" | "neutral"> = {
  empty: "neutral",
  uploaded: "info",
  parsed: "warn",
  analyzed: "ok",
  error: "warn",
};

export default function WorkCard({ work, isActive, onSelect }: Props) {
  return (
    <div
      onClick={() => onSelect(work.id)}
      style={{
        cursor: "pointer",
        padding: "0.5rem 0.6rem",
        marginBottom: "0.3rem",
        borderRadius: 4,
        border: isActive ? "2px solid #1976d2" : "1px solid #e0e0e0",
        background: isActive ? "#e3f2fd" : "#fff",
        transition: "background 0.15s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontWeight: 600, fontSize: "0.88rem" }}>
          {work.series_index != null && `${work.series_index}. `}
          {work.title}
        </span>
        <StatusBadge label={work.status} tone={STATUS_TONES[work.status] || "neutral"} />
      </div>
      {work.author && (
        <span className="text-dim" style={{ fontSize: "0.72rem" }}>
          {work.author}
        </span>
      )}
    </div>
  );
}
