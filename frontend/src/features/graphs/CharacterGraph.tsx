import { useQuery } from "@tanstack/react-query";
import { getCharacterGraph } from "../../api/graphs";
import LoadingBlock from "../../components/LoadingBlock";

interface Props {
  topicId: string;
}

export default function CharacterGraph({ topicId }: Props) {
  const graphQuery = useQuery({
    queryKey: ["graph", topicId],
    queryFn: () => getCharacterGraph(topicId, { include_evidence: false }),
  });

  if (graphQuery.isLoading) return <LoadingBlock text="Loading graph..." />;

  const data = graphQuery.data;
  const nodeCount = data?.nodes?.length ?? 0;
  const edgeCount = data?.edges?.length ?? 0;

  return (
    <div>
      <h3 style={{ margin: "0 0 0.5rem 0" }}>Character Relationship Graph</h3>

      {nodeCount === 0 ? (
        <p className="text-dim" style={{ fontSize: "0.85rem" }}>
          No graph data yet. Run a cross-work build to generate the character relationship graph.
        </p>
      ) : (
        <div>
          <p style={{ fontSize: "0.82rem", marginBottom: "0.4rem" }}>
            {nodeCount} characters · {edgeCount} relationships
          </p>
          <div style={{
            maxHeight: "400px",
            overflow: "auto",
            border: "1px solid #e0e0e0",
            borderRadius: 4,
            padding: "0.5rem",
            background: "#fafafa",
          }}>
            <table style={{ width: "100%", fontSize: "0.78rem", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                  <th>Character A</th>
                  <th>Relation</th>
                  <th>Character B</th>
                  <th>Weight</th>
                </tr>
              </thead>
              <tbody>
                {data?.edges?.slice(0, 50).map((edge) => {
                  const src = data.nodes.find((n) => n.id === edge.source);
                  const tgt = data.nodes.find((n) => n.id === edge.target);
                  return (
                    <tr key={edge.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                      <td style={{ fontWeight: 600 }}>{src?.label || edge.source.slice(0, 8)}</td>
                      <td style={{ color: "#666" }}>{edge.relation_type}</td>
                      <td style={{ fontWeight: 600 }}>{tgt?.label || edge.target.slice(0, 8)}</td>
                      <td>{edge.weight}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {data?.snapshot_id && (
            <p className="text-dim" style={{ fontSize: "0.7rem", marginTop: "0.3rem" }}>
              Snapshot: {data.snapshot_id}
              {data.generated_at && ` · Generated: ${new Date(data.generated_at).toLocaleString()}`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
