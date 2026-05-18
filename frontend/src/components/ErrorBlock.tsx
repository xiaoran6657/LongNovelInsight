interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorBlock({ title, message, onRetry }: Props) {
  return (
    <div className="card card-error" style={{ padding: "1rem" }}>
      <p style={{ fontWeight: 700, marginBottom: "0.35rem" }}>
        {title || "Error"}
      </p>
      <p style={{ fontSize: "0.88rem", marginBottom: onRetry ? "0.75rem" : 0 }}>
        {message}
      </p>
      {onRetry && (
        <button onClick={onRetry} style={{ fontSize: "0.82rem" }}>
          Retry
        </button>
      )}
    </div>
  );
}
