type StatusTone = "ok" | "warn" | "error" | "info" | "neutral";

interface Props {
  label: string;
  tone?: StatusTone;
}

const TONE_STYLES: Record<StatusTone, { bg: string; fg: string; border: string }> = {
  ok:    { bg: "#e8f5e9", fg: "#2e7d32", border: "#a5d6a7" },
  warn:  { bg: "#fff8e1", fg: "#f57f17", border: "#ffe082" },
  error: { bg: "#ffebee", fg: "#c62828", border: "#ef9a9a" },
  info:  { bg: "#e3f2fd", fg: "#1565c0", border: "#90caf9" },
  neutral: { bg: "#f5f5f5", fg: "#616161", border: "#e0e0e0" },
};

export default function StatusBadge({ label, tone = "neutral" }: Props) {
  const s = TONE_STYLES[tone];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.12em 0.5em",
        fontSize: "0.72rem",
        fontWeight: 600,
        borderRadius: 4,
        background: s.bg,
        color: s.fg,
        border: `1px solid ${s.border}`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

export function statusTone(tone?: StatusTone): StatusTone {
  return tone || "neutral";
}
