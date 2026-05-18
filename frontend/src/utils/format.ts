/**
 * Format a byte count into a human-readable string (KB, MB, GB).
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/**
 * Format an ISO timestamp string into a short locale string.
 */
export function formatDateTime(iso: string): string {
  try {
    const normalized = /[+\-Zz]\d*$/.test(iso.trimEnd()) ? iso : iso + "Z";
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * Format a JSON value as a single-line truncated preview (for list/dashboard use).
 */
export function formatJsonPreview(value: unknown, maxLen: number = 80): string {
  if (value === null || value === undefined) return "—";
  try {
    const s = typeof value === "string" ? value : JSON.stringify(value);
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen) + "…";
  } catch {
    return String(value);
  }
}
