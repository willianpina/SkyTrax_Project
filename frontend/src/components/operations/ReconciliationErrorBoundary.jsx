import React from "react";
import { AlertTriangle } from "lucide-react";

export class ReconciliationErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    if (import.meta.env?.DEV) {
      console.warn("[RECONCILIATION_SAFE] ErrorBoundary caught:", error, info?.componentStack);
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="osm-integrity-strip osm-integrity-strip--fallback" role="status">
          <AlertTriangle size={12} />
          <span>
            {this.props.fallbackLabel ||
              "Pipeline integrity unavailable — partial operational data may still be shown below."}
          </span>
        </div>
      );
    }
    return this.props.children;
  }
}
