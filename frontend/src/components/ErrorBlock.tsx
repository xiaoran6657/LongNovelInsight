interface Props {
  title?: string;
  message: string;
  detail?: string;
  status?: number;
  onRetry?: () => void;
}

export default function ErrorBlock({ title, message, detail, status, onRetry }: Props) {
  const truncated = detail && detail.length > 500 ? detail.slice(0, 500) + "..." : detail;

  return (
    <div className="card card-error" style={{ padding: "1rem" }}>
      <p style={{ fontWeight: 700, marginBottom: "0.35rem" }}>
        {status != null && (
          <span className="error-status-badge">
            [{status === 0 ? "network" : status}]
          </span>
        )}
        {title || "Error"}
      </p>
      <p style={{ fontSize: "0.88rem", marginBottom: detail || onRetry ? "0.5rem" : 0 }}>
        {message}
      </p>
      {truncated && (
        <details className="error-detail">
          <summary style={{ cursor: "pointer", fontSize: "0.78rem", color: "#c62828", fontWeight: 600 }}>
            Show details
          </summary>
          <pre className="error-detail-pre">{truncated}</pre>
        </details>
      )}
      {onRetry && (
        <button onClick={onRetry} style={{ fontSize: "0.82rem", marginTop: detail ? "0.5rem" : 0 }}>
          Retry
        </button>
      )}
    </div>
  );
}
