import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  outputType: string;
};

type State = {
  hasError: boolean;
};

export default class AnalysisOutputErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Failed to render analysis output", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="card"
          role="alert"
          style={{ background: "#ffebee", borderColor: "#ffcdd2", marginBottom: "0.75rem" }}
        >
          <strong style={{ color: "#c62828" }}>Unable to render this output</strong>
          <p className="text-dim" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
            The {this.props.outputType || "analysis"} result has an unexpected shape. Other
            outputs remain available.
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}
