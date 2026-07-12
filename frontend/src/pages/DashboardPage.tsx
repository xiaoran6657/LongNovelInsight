import HealthPanel from "../components/HealthPanel";

export default function DashboardPage() {
  return (
    <div>
      <h2>Dashboard</h2>

      <HealthPanel />

      <section className="card" style={{ marginTop: "1.5rem" }}>
        <h3>v0.4.0 Workflow</h3>
        <ol className="workflow-list">
          <li>
            <strong>Configure Provider</strong> — Add an LLM provider
            (DeepSeek or OpenAI-compatible) on the Providers page.
          </li>
          <li>
            <strong>Create Topic and Work</strong> — Create a story-universe
            workspace, add a novel or volume, and optionally bind a provider.
          </li>
          <li>
            <strong>Upload Novel</strong> — Upload one <code>.txt</code> or
            <code>.epub</code> source to the Work. TXT inputs support UTF-8 and
            GBK/GB18030 encodings.
          </li>
          <li>
            <strong>Parse</strong> — Auto-detect chapters and split into
            chunks for analysis.
          </li>
          <li>
            <strong>Run Analysis</strong> — Generate structured analysis
            outputs (overview, characters, relations, events, causality,
            themes).
          </li>
          <li>
            <strong>Chat</strong> — Ask questions grounded in the evidence
            from the novel and analysis.
          </li>
          <li>
            <strong>Compare Works</strong> — Build the cross-work entity
            registry, relationship graph, and timeline for a Topic.
          </li>
        </ol>
      </section>
    </div>
  );
}
