import type { SourceLocator } from "../../api/types";

interface Props {
  sourceLocatorJson?: string | null;
  fileType?: "txt" | "epub";
  chapterIndex?: number;
  chunkIndex?: number;
}

function parseLocator(raw: string | null | undefined): SourceLocator {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as SourceLocator;
    }
  } catch {
    // ignore
  }
  return {};
}

function abbreviateHref(href: string): string {
  const parts = href.split("/");
  return parts[parts.length - 1] || href;
}

export default function SourceLocatorBadge({
  sourceLocatorJson,
  fileType,
  chapterIndex,
  chunkIndex,
}: Props) {
  const loc = parseLocator(sourceLocatorJson);
  const href = typeof loc.source_href === "string" ? loc.source_href : null;
  const effectiveType = fileType ?? (href ? "epub" : "txt");

  let label: string;
  if (effectiveType === "epub" && href) {
    label = `EPUB: ${abbreviateHref(href)}`;
  } else if (effectiveType === "epub") {
    label = "EPUB source";
  } else {
    label = "TXT source";
  }

  const chapterLabel =
    chapterIndex != null ? `Ch.${chapterIndex}` : "";
  const chunkLabel = chunkIndex != null ? `#${chunkIndex}` : "";
  const detail = [chapterLabel, chunkLabel].filter(Boolean).join(" ");
  const title = href ?? undefined;

  return (
    <span
      className="text-dim"
      title={title}
      style={{
        fontSize: "0.7rem",
        padding: "0.1rem 0.35rem",
        borderRadius: 3,
        background: effectiveType === "epub" ? "#e8f5e9" : "#f5f5f5",
        color: effectiveType === "epub" ? "#2e7d32" : "#757575",
        border: `1px solid ${effectiveType === "epub" ? "#a5d6a7" : "#e0e0e0"}`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
      {detail && <span style={{ marginLeft: "0.3rem" }}>{detail}</span>}
    </span>
  );
}
