import { useQuery } from "@tanstack/react-query";
import { getTimeline } from "../../api/timeline";
import type { TimelineItem } from "../../api/types";
import LoadingBlock from "../../components/LoadingBlock";

interface Props {
  topicId: string;
}

export default function TimelineView({ topicId }: Props) {
  const timelineQuery = useQuery({
    queryKey: ["timeline", topicId],
    queryFn: () => getTimeline(topicId, { limit: 100 }),
  });

  if (timelineQuery.isLoading) return <LoadingBlock text="Loading timeline..." />;

  const items: TimelineItem[] = timelineQuery.data?.items ?? [];

  return (
    <div>
      <h3 style={{ margin: "0 0 0.5rem 0" }}>Timeline</h3>

      {items.length === 0 ? (
        <p className="text-dim" style={{ fontSize: "0.85rem" }}>
          No timeline events yet. Run a cross-work build to generate the event timeline.
        </p>
      ) : (
        <div>
          <p style={{ fontSize: "0.82rem", marginBottom: "0.4rem" }}>
            {timelineQuery.data?.total ?? items.length} events
          </p>
          <div style={{ maxHeight: "400px", overflow: "auto" }}>
            {items.map((item) => (
              <div
                key={item.id}
                className="card"
                style={{
                  marginBottom: "0.3rem",
                  padding: "0.4rem 0.6rem",
                  fontSize: "0.82rem",
                  borderLeft: "3px solid #1976d2",
                }}
              >
                <div style={{ fontWeight: 600 }}>{item.title}</div>
                {item.summary && (
                  <p className="text-dim" style={{ fontSize: "0.75rem", margin: "0.15rem 0" }}>
                    {item.summary}
                  </p>
                )}
                <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.72rem", color: "#888" }}>
                  {item.time_label && <span>{item.time_label}</span>}
                  {item.work_id && <span>Work: {item.work_id.slice(0, 8)}</span>}
                  {item.sequence_index != null && (
                    <span>Seq: {item.sequence_index.toFixed(0)}</span>
                  )}
                  {item.confidence > 0 && (
                    <span>Conf: {item.confidence.toFixed(2)}</span>
                  )}
                </div>
                {item.participants?.length > 0 && (
                  <p style={{ fontSize: "0.72rem", marginTop: "0.15rem" }}>
                    Participants: {item.participants.join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
