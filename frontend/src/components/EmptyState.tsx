interface Props {
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({ icon, title, description, action }: Props) {
  return (
    <div className="card" style={{ textAlign: "center", padding: "2.5rem 1.5rem" }}>
      {icon && (
        <p style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>{icon}</p>
      )}
      <p style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: "0.3rem" }}>
        {title}
      </p>
      {description && (
        <p className="text-dim" style={{ marginBottom: action ? "1rem" : 0 }}>
          {description}
        </p>
      )}
      {action && (
        <button onClick={action.onClick} style={{ fontSize: "0.85rem" }}>
          {action.label}
        </button>
      )}
    </div>
  );
}
