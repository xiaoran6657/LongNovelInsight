import { useParams } from "react-router-dom";

export default function TopicChatPage() {
  const { topicId } = useParams<{ topicId: string }>();

  return (
    <div>
      <h2>Chat</h2>
      <div className="card">
        <p className="text-dim">
          Chat for Topic <code>{topicId}</code> will be implemented in Task 008.
        </p>
      </div>
    </div>
  );
}
