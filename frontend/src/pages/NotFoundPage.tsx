import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div style={{ textAlign: "center", padding: "3rem 0" }}>
      <h2>Page Not Found</h2>
      <p className="text-dim" style={{ marginBottom: "1rem" }}>
        The page you are looking for does not exist.
      </p>
      <Link to="/">Back to Dashboard</Link>
    </div>
  );
}
