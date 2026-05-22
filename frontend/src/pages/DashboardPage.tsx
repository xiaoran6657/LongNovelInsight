import HealthPanel from "../components/HealthPanel";

export default function DashboardPage() {
  return (
    <div>
      <h2>Dashboard</h2>

      <HealthPanel />

      <section className="card" style={{ marginTop: "1.5rem" }}>
        <h3>v0.2.0 Workflow</h3>
        <ol className="workflow-list">
          <li>
            <strong>Configure Provider</strong> — Add an LLM provider
            (DeepSeek or OpenAI-compatible) on the Providers page.
          </li>
          <li>
            <strong>Create Topic</strong> — Create a workspace and optionally
            bind a provider.
          </li>
          <li>
            <strong>Upload Novel</strong> — Upload a <code>.txt</code> novel
            file to the topic. UTF-8 and GBK/GB18030 encodings are accepted.
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
        </ol>
      </section>
    </div>
  );
}
