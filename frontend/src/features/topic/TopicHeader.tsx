import { Link } from "react-router-dom";
import type { Topic } from "../../api/types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

interface Props {
  topic: Topic;
}

export default function TopicHeader({ topic }: Props) {
  return (
    <div>
      <p style={{ marginBottom: "1rem" }}>
        <Link to="/topics">&larr; Back to Topics</Link>
        {" | "}
        <Link to={`/topics/${topic.id}/chat`}>Chat &rarr;</Link>
      </p>
      <h2>{topic.name}</h2>
      <div className="card">
        <h3>Info</h3>
        <p>
          <strong>Status:</strong>{" "}
          <span className={`status-badge status-${topic.status}`}>
            {topic.status}
          </span>
        </p>
        {topic.description && (
          <p><strong>Description:</strong> {topic.description}</p>
        )}
        <p>
          <strong>Storage:</strong> {formatBytes(topic.disk_usage_bytes ?? 0)}
        </p>
        <p className="text-dim" style={{ fontSize: "0.85rem" }}>
          Created: {formatDate(topic.created_at)}
          {" · "}
          Updated: {formatDate(topic.updated_at)}
        </p>
      </div>
    </div>
  );
}
