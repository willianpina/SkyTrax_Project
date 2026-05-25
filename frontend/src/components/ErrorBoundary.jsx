import React from "react";
import i18n from "../i18n";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || "Unknown render error" };
  }

  componentDidCatch(error, info) {
    console.error("dashboard_render_error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="command-boot error-state">
          <h2>{i18n.t("common:error.title")}</h2>
          <p>{this.state.message}</p>
          <button type="button" className="tactical-btn" onClick={() => window.location.reload()}>
            {i18n.t("common:actions.retry")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
