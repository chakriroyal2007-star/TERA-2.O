import React, { Component, ErrorInfo, ReactNode } from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { queryClient } from "./api";
import { App } from "./App";
import "leaflet/dist/leaflet.css";
import "./styles.css";

class GlobalErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null };
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Global application boundary caught error:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "#091412",
            color: "#f8fafc",
            fontFamily: "system-ui, sans-serif",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <div
            style={{
              maxWidth: "520px",
              background: "#102824",
              border: "1px solid #1a3c36",
              borderRadius: "12px",
              padding: "2.5rem",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>⚡</div>
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.4rem", color: "#34d399" }}>
              TERA Emergency Operations Workspace
            </h2>
            <p style={{ color: "#94a3b8", fontSize: "0.95rem", lineHeight: "1.5", margin: "0 0 1.5rem" }}>
              The workspace encountered a recoverable state change. Click below to refresh your session.
            </p>
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  background: "#10b981",
                  color: "#052e16",
                  border: "none",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  cursor: "pointer",
                }}
              >
                Reload Workspace
              </button>
              <button
                type="button"
                onClick={() => {
                  window.location.href = "/app";
                }}
                style={{
                  background: "transparent",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  cursor: "pointer",
                }}
              >
                Incident Desk
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <GlobalErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </GlobalErrorBoundary>
  </React.StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("ServiceWorker registration skipped:", err);
    });
  });
}
