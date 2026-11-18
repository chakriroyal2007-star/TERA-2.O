import { lazy, Suspense, Component, ReactNode, ErrorInfo } from "react";
import { Loading } from "./components";
import type {
  Point,
  RoutePolyline,
  AmbulanceMarkerProps,
  IncidentMarkerProps,
  HospitalMarkerProps,
  MapProps,
} from "./MapView";
export type {
  Point,
  RoutePolyline,
  AmbulanceMarkerProps,
  IncidentMarkerProps,
  HospitalMarkerProps,
  MapProps,
} from "./MapView";

class MapErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error?: Error }> {
  state: { hasError: boolean; error?: Error } = { hasError: false };
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn("Leaflet Map warning caught gracefully:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "2rem",
            textAlign: "center",
            background: "rgba(15, 23, 42, 0.9)",
            borderRadius: "10px",
            color: "#f8fafc",
            border: "1px solid #334155",
            minHeight: "360px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
          }}
        >
          <span style={{ fontSize: "28px" }}>🗺️</span>
          <strong style={{ fontSize: "14px", color: "#38bdf8" }}>Tactical Map Renderer</strong>
          <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8", maxWidth: "340px" }}>
            Map coordinates updating. Refreshing spatial viewport...
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false })}
            style={{
              background: "#0284c7",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              padding: "6px 14px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Reload Map View
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const MapView = lazy(() =>
  import("./MapView").then((module) => ({ default: module.Map })),
);

export function Map(props: MapProps) {
  return (
    <MapErrorBoundary>
      <Suspense fallback={<Loading />}>
        <MapView {...props} />
      </Suspense>
    </MapErrorBoundary>
  );
}
