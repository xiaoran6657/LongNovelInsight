import { useState, useMemo } from "react";
import type { Chapter } from "../../api/types";

interface Props {
  chapters: Chapter[];
}

function abbreviateHref(href: string): string {
  const parts = href.split("/");
  return parts[parts.length - 1] || href;
}

export default function EpubChapterTree({ chapters }: Props) {
  const [expanded, setExpanded] = useState(true);

  const { sorted, hasEpubMeta } = useMemo(() => {
    const s = [...chapters].sort((a, b) => {
      const aNav = a.nav_order ?? a.chapter_index;
      const bNav = b.nav_order ?? b.chapter_index;
      return aNav - bNav;
    });
    const hasMeta = s.some(
      (ch) => ch.source_href || ch.nav_order != null
    );
    return { sorted: s, hasEpubMeta: hasMeta };
  }, [chapters]);
  if (!hasEpubMeta) return null;

  return (
    <div className="card">
      <h3
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: "pointer", userSelect: "none" }}
      >
        {expanded ? "▾" : "▸"} EPUB Chapter Tree{" "}
        <span className="text-dim">({sorted.length})</span>
      </h3>
      {expanded && (
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          {sorted.map((ch) => (
            <div
              key={ch.id}
              style={{
                padding: "0.3rem 0",
                borderBottom: "1px solid #eee",
                fontSize: "0.82rem",
                display: "flex",
                alignItems: "baseline",
                gap: "0.5rem",
              }}
            >
              <span style={{ minWidth: "2.5rem", color: "#888" }}>
                #{ch.chapter_index + 1}
              </span>
              <span style={{ flex: 1 }}>{ch.title}</span>
              {ch.source_href && (
                <span
                  className="text-dim"
                  style={{ fontSize: "0.72rem" }}
                  title={ch.source_href}
                >
                  {abbreviateHref(ch.source_href)}
                </span>
              )}
              {ch.nav_order != null && (
                <span
                  style={{
                    fontSize: "0.68rem",
                    color: "#aaa",
                    minWidth: "1.5rem",
                    textAlign: "right",
                  }}
                >
                  [{ch.nav_order}]
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
