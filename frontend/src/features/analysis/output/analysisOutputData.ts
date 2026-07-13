export type AnalysisOutputBlockProps = {
  json: Record<string, unknown>;
  evidence: string[];
  chunks: string[];
};

export type FormattedConfidence = {
  text: string;
  color: string;
};

export function formatConfidence(c: number | null | undefined): FormattedConfidence {
  if (c == null || isNaN(c)) return { text: "unknown", color: "#999" };
  if (c >= 0.7) return { text: `${(c * 100).toFixed(0)}%`, color: "#27ae60" };
  if (c >= 0.4) return { text: `${(c * 100).toFixed(0)}%`, color: "#f57f17" };
  return { text: `${(c * 100).toFixed(0)}%`, color: "#e74c3c" };
}

export function collectItemConfidences(json: Record<string, unknown>): number[] {
  const results: number[] = [];
  for (const [, value] of Object.entries(json)) {
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (
        item &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).confidence === "number"
      ) {
        const confidence = (item as Record<string, unknown>).confidence as number;
        if (!isNaN(confidence)) results.push(confidence);
      }
    }
  }
  return results;
}

export function inferConfidence(
  outputConfidence: number,
  json: Record<string, unknown> | null,
): number | null {
  if (json && json.insufficient_evidence) return null;
  if (outputConfidence > 0) return outputConfidence;
  if (!json) return null;
  const items = collectItemConfidences(json);
  if (items.length === 0) return null;
  return items.reduce((a, b) => a + b, 0) / items.length;
}

export function getString(value: unknown, fallback: string = "—"): string {
  if (typeof value === "string" && value.trim()) return value;
  return fallback;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function normalizeContent(value: unknown): {
  json: Record<string, unknown>;
  malformed: boolean;
} {
  if (value == null) return { json: {}, malformed: false };
  if (isRecord(value)) return { json: value, malformed: false };
  if (typeof value === "string") {
    try {
      const parsed: unknown = JSON.parse(value);
      if (isRecord(parsed)) return { json: parsed, malformed: false };
    } catch {
      // The warning UI handles invalid serialized JSON.
    }
  }
  return { json: {}, malformed: true };
}

export function getRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord);
}

export function getStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string") return item.trim() ? [item] : [];
    if (typeof item === "number" || typeof item === "boolean") return [String(item)];
    return [];
  });
}

export function hasAnyEvidence(items: unknown[]): boolean {
  for (const item of items) {
    if (item && typeof item === "object") {
      const evidence = (item as Record<string, unknown>).evidence_quotes;
      if (Array.isArray(evidence) && evidence.length > 0) return true;
    }
  }
  return false;
}
