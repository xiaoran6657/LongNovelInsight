import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../api/health";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export default function HealthPanel() {
  const { data, isLoading, error, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchOnWindowFocus: false,
  });

  if (isLoading) {
    return (
      <div className="card">
        <p className="text-dim">Checking backend connection...</p>
      </div>
    );
  }

  if (isError) {
    const msg =
      error instanceof Error
        ? error.message
        : "Cannot reach backend. Is it running on port 8000?";
    return (
      <div className="card card-error">
        <p>
          <strong>Backend: Disconnected</strong>
        </p>
        <p className="text-dim">{msg}</p>
      </div>
    );
  }

  if (!data) return null;

  const statusClass =
    data.status === "ok" ? "status-ok" : "status-fail";

  return (
    <div className="card">
      <p>
        <strong>Backend:</strong>{" "}
        <span className={statusClass}>{data.status}</span>
      </p>
      <p>
        <strong>Version:</strong> {data.version}
      </p>
      <p>
        <strong>Topics:</strong> {data.topic_count}
      </p>
      <p>
        <strong>Disk Usage:</strong> {formatBytes(data.total_disk_usage_bytes)}
      </p>
    </div>
  );
}
