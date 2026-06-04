import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listEntities, getEntity, listEntityMentions } from "../../api/crossWork";
import type { GlobalEntity, EntityMention } from "../../api/types";
import LoadingBlock from "../../components/LoadingBlock";
import ErrorBlock from "../../components/ErrorBlock";

interface Props {
  topicId: string;
}

export default function EntityRegistryTable({ topicId }: Props) {
  const [entityType, setEntityType] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("mention_count");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const entitiesQuery = useQuery({
    queryKey: ["entities", topicId, entityType, query, sort],
    queryFn: () =>
      listEntities(topicId, {
        entity_type: entityType || undefined,
        q: query || undefined,
        sort,
        limit: 100,
      }),
  });

  return (
    <div>
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
        <input
          type="text"
          placeholder="Search by name..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: "180px", fontSize: "0.8rem" }}
        />
        <select value={entityType} onChange={(e) => setEntityType(e.target.value)}
          style={{ fontSize: "0.8rem" }}>
          <option value="">All types</option>
          <option value="character">Character</option>
          <option value="location">Location</option>
          <option value="organization">Organization</option>
          <option value="concept">Concept</option>
          <option value="item">Item</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}
          style={{ fontSize: "0.8rem" }}>
          <option value="mention_count">Most mentions</option>
          <option value="name">Name A-Z</option>
          <option value="confidence">Highest confidence</option>
          <option value="work_count">Most Works</option>
        </select>
      </div>

      {entitiesQuery.isLoading && <LoadingBlock text="Loading entities..." />}
      {entitiesQuery.isError && <ErrorBlock message="Failed to load entities" />}

      {entitiesQuery.isSuccess && entitiesQuery.data.total === 0 && (
        <p className="text-dim" style={{ fontSize: "0.8rem" }}>
          No entities found. Run a cross-work build first.
        </p>
      )}

      {entitiesQuery.isSuccess && entitiesQuery.data.entities.length > 0 && (
        <table style={{ width: "100%", fontSize: "0.8rem", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
              <th style={{ padding: "0.2rem 0.4rem" }}>Name</th>
              <th>Type</th>
              <th>Mentions</th>
              <th>Works</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {entitiesQuery.data.entities.map((e: GlobalEntity) => (
              <tr
                key={e.id}
                onClick={() => setSelectedId(selectedId === e.id ? null : e.id)}
                style={{
                  borderBottom: "1px solid #f0f0f0",
                  cursor: "pointer",
                  background: selectedId === e.id ? "#e3f2fd" : "transparent",
                }}
              >
                <td style={{ padding: "0.2rem 0.4rem", fontWeight: 600 }}>{e.canonical_name}</td>
                <td>{e.entity_type}</td>
                <td>{e.mention_count}</td>
                <td>{e.work_ids.length}</td>
                <td>{e.confidence.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedId && (
        <EntityDetailDrawer topicId={topicId} entityId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}

function EntityDetailDrawer({
  topicId,
  entityId,
  onClose,
}: {
  topicId: string;
  entityId: string;
  onClose: () => void;
}) {
  const entityQuery = useQuery({
    queryKey: ["entity", topicId, entityId],
    queryFn: () => getEntity(topicId, entityId),
  });

  const mentionsQuery = useQuery({
    queryKey: ["entity-mentions", topicId, entityId],
    queryFn: () => listEntityMentions(topicId, entityId, 20, 0),
  });

  const entity = entityQuery.data;

  return (
    <div className="card" style={{ marginTop: "0.5rem", background: "#fafafa" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h4 style={{ margin: 0 }}>Entity Detail</h4>
        <button onClick={onClose} style={{ fontSize: "0.7rem", padding: "0.1em 0.4em" }}>×</button>
      </div>
      {entityQuery.isLoading && <LoadingBlock text="Loading..." />}
      {entity && (
        <div style={{ fontSize: "0.82rem", marginTop: "0.4rem" }}>
          <p><strong>Name:</strong> {entity.canonical_name}</p>
          <p><strong>Type:</strong> {entity.entity_type}</p>
          <p><strong>Aliases:</strong> {entity.aliases?.join(", ") || "—"}</p>
          <p><strong>Works:</strong> {entity.work_ids?.length || 0}</p>
          <p><strong>Confidence:</strong> {entity.confidence.toFixed(2)} ·{" "}
            <strong>Strategy:</strong> {entity.merge_strategy}</p>
        </div>
      )}
      {mentionsQuery.isSuccess && (
        <p style={{ fontSize: "0.78rem", marginTop: "0.3rem" }}>
          <strong>Mentions:</strong> {mentionsQuery.data.total}
          {mentionsQuery.data.mentions.slice(0, 5).map((m: EntityMention, i: number) => (
            <span key={m.id} className="text-dim" style={{ display: "block", fontSize: "0.72rem" }}>
              #{i + 1} {m.surface_text} {m.evidence_text && `— "${m.evidence_text.slice(0, 80)}"`}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
