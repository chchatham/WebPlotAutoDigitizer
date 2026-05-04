import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  error: string | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error);
    return { error: message };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, textAlign: "center" }}>
          <h2 style={{ color: "#dc2626" }}>Something went wrong</h2>
          <p style={{ color: "#6b7280", marginBottom: 16 }}>{this.state.error}</p>
          <button
            onClick={() => {
              this.setState({ error: null });
              this.props.onReset?.();
            }}
          >
            Start over
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
