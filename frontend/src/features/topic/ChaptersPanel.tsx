import type { Chapter } from "../../api/types";

interface Props {
  chapters: Chapter[] | undefined;
}

export default function ChaptersPanel({ chapters }: Props) {
  if (!chapters || chapters.length === 0) return null;
  return (
    <div className="card">
      <h3>Chapters{" "}<span className="text-dim">({chapters.length})</span></h3>
      <div style={{ maxHeight: 300, overflowY: "auto" }}>
        {chapters.map((ch) => (
          <div key={ch.id} style={{ padding: "0.25rem 0", borderBottom: "1px solid #eee", fontSize: "0.85rem" }}>
            <strong>Ch. {ch.chapter_index + 1}</strong> — {ch.title}{" "}
            <span className="text-dim">({ch.char_count.toLocaleString()} chars)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
