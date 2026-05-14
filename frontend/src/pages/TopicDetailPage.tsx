import { useParams } from "react-router-dom";

export default function TopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();

  return (
    <div>
      <h2>Topic Detail</h2>
      <div className="card">
        <p className="text-dim">
          Topic <code>{topicId}</code> detail will be implemented in later tasks.
        </p>
      </div>
    </div>
  );
}
