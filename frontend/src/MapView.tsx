import { useEffect, useState, useMemo, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMapEvents,
  useMap,
  Polyline,
  Marker,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet's default icon url issues in bundled environments
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export interface Point {
  latitude: number | null;
  longitude: number | null;
  name: string;
  detail?: string;
}

export interface RoutePolyline {
  coordinates: [number, number][];
  color?: string;
  weight?: number;
  opacity?: number;
  dashArray?: string;
  label?: string;
  completedCoordinates?: [number, number][];
}

export interface AmbulanceMarkerProps {
  id?: string;
  latitude: number;
  longitude: number;
  label?: string;
  driverName?: string;
  driverPhone?: string;
  registration?: string;
  stale?: boolean;
  ageSeconds?: number;
  speed?: number;
  heading?: number;
  status?: string;
  vehicleType?: string;
  patientCapacity?: number;
  assignedIncident?: string;
  destinationHospital?: string;
}

export interface IncidentMarkerProps {
  id?: string;
  latitude: number;
  longitude: number;
  label?: string;
  case_id?: string;
  address?: string;
  priority?: string;
  category?: string;
  casualties_count?: number;
  status?: string;
  created_at?: string;
  priority_score?: number;
}

export interface HospitalMarkerProps {
  id?: string;
  name: string;
  latitude: number;
  longitude: number;
  hospital_type?: string;
  address?: string;
  emergency_phone?: string;
  available_beds?: {
    icu?: number;
    emergency?: number;
    general?: number;
    total?: number;
  };
  total_available_beds?: number;
  icu_beds?: number;
  emergency_beds?: number;
  diversion_status?: boolean;
  occupancy_pct?: number;
}

export interface MapProps {
  points?: Point[];
  routes?: RoutePolyline[];
  ambulance?: AmbulanceMarkerProps | null;
  incident?: IncidentMarkerProps | null;
  ambulances?: AmbulanceMarkerProps[];
  incidents?: IncidentMarkerProps[];
  hospitals?: HospitalMarkerProps[];
  trail?: [number, number][];
  onLocationSelect?: (lat: number, lng: number) => void;
  onSelectIncident?: (incident: IncidentMarkerProps) => void;
  onSelectAmbulance?: (ambulance: AmbulanceMarkerProps) => void;
  onSelectHospital?: (hospital: HospitalMarkerProps) => void;
  selectedIncidentId?: string | null;
  selectedAmbulanceId?: string | null;
  interactive?: boolean;
  simulationMode?: boolean;
  showControls?: boolean;
  height?: string;
}

// ============================================================================
// CUSTOM VECTOR MARKER GENERATORS (Recognizable, crisp, responsive)
// ============================================================================

function createEmergencyMarkerIcon(inc: IncidentMarkerProps, isSelected: boolean = false) {
  const isCritical = (inc.priority || "").toLowerCase() === "critical";
  const isHigh = (inc.priority || "").toLowerCase() === "high";

  const bgColor = isCritical ? "#ef4444" : isHigh ? "#f97316" : "#3b82f6";
  const pulseClass = isCritical ? "marker-emergency-critical" : "";
  const borderStyle = isSelected ? "3px solid #ffffff" : "2px solid rgba(255, 255, 255, 0.9)";
  const scale = isSelected ? "transform: scale(1.15);" : "";
  const patientsBadge = inc.casualties_count && inc.casualties_count > 1
    ? `<span style="position: absolute; bottom: -4px; right: -6px; background: #0f172a; color: #f8fafc; font-size: 10px; font-weight: 800; padding: 1px 4px; border-radius: 8px; border: 1px solid #ffffff;">${inc.casualties_count}p</span>`
    : "";

  return L.divIcon({
    className: "custom-incident-div-icon",
    html: `
      <div class="${pulseClass}" style="
        position: relative;
        background: ${bgColor};
        ${borderStyle}
        border-radius: 50%;
        width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
        cursor: pointer;
        transition: transform 0.2s ease;
        ${scale}
      ">
        <span style="font-size: 19px; line-height: 1;">🚨</span>
        ${patientsBadge}
      </div>
    `,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
}

function createAmbulanceMarkerIcon(amb: AmbulanceMarkerProps, isSelected: boolean = false) {
  const st = (amb.status || "available").toLowerCase();
  const isBusy = st === "transporting" || st === "on_scene";
  const isAssigned = st === "assigned" || st === "en_route" || st === "acknowledged";

  const statusBadgeColor = isBusy ? "#f59e0b" : isAssigned ? "#0284c7" : "#10b981";
  const pulseClass = isAssigned ? "marker-ambulance-active" : "";
  const borderHighlight = isSelected ? "border: 2px solid #38bdf8;" : "border: 2px solid #334155;";

  const speedTag = amb.speed && amb.speed > 0
    ? `<span style="position: absolute; bottom: -7px; left: 50%; transform: translateX(-50%); background: #0284c7; color: #ffffff; font-size: 9px; font-weight: 800; padding: 1px 5px; border-radius: 4px; white-space: nowrap;">${Math.round(amb.speed)} km/h</span>`
    : "";

  return L.divIcon({
    className: "custom-ambulance-div-icon",
    html: `
      <div class="${pulseClass}" style="
        position: relative;
        background: #ffffff;
        ${borderHighlight}
        border-radius: 50%;
        width: 42px;
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
        cursor: pointer;
        transition: transform 0.3s ease;
        ${isSelected ? "transform: scale(1.15);" : ""}
      ">
        <span style="font-size: 22px; line-height: 1;">🚑</span>
        <span style="
          position: absolute;
          top: -2px;
          right: -2px;
          width: 12px;
          height: 12px;
          background: ${statusBadgeColor};
          border: 2px solid #ffffff;
          border-radius: 50%;
        "></span>
        ${speedTag}
      </div>
    `,
    iconSize: [42, 42],
    iconAnchor: [21, 21],
    popupAnchor: [0, -22],
  });
}

function createHospitalMarkerIcon(hosp: HospitalMarkerProps, isSelected: boolean = false) {
  const isDiversion = hosp.diversion_status;
  const availBeds = hosp.available_beds?.emergency ?? hosp.emergency_beds ?? hosp.total_available_beds ?? 0;
  const icuBeds = hosp.available_beds?.icu ?? hosp.icu_beds ?? 0;
  const ringColor = isDiversion ? "#ef4444" : "#0284c7";

  return L.divIcon({
    className: "custom-hospital-div-icon",
    html: `
      <div style="
        position: relative;
        background: #0f172a;
        border: 2px solid ${ringColor};
        border-radius: 8px;
        width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4);
        cursor: pointer;
        transition: transform 0.2s ease;
        ${isSelected ? "transform: scale(1.15);" : ""}
      ">
        <span style="font-size: 20px; line-height: 1;">🏥</span>
        <span style="
          position: absolute;
          top: -6px;
          right: -8px;
          background: ${isDiversion ? "#ef4444" : "#10b981"};
          color: #ffffff;
          font-size: 9px;
          font-weight: 800;
          padding: 1px 4px;
          border-radius: 6px;
          border: 1px solid #0f172a;
          white-space: nowrap;
        ">
          ${isDiversion ? "FULL" : `${availBeds + icuBeds}b`}
        </span>
      </div>
    `,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
}

// ============================================================================
// MAP EVENT & SIZING LISTENERS
// ============================================================================

function ClickHandler({ onLocationSelect }: { onLocationSelect?: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      if (onLocationSelect) {
        onLocationSelect(Number(e.latlng.lat.toFixed(6)), Number(e.latlng.lng.toFixed(6)));
      }
    },
  });
  return null;
}

function InvalidateSizeHandler() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 120);
    const handleResize = () => map.invalidateSize();
    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResize);
    };
  }, [map]);
  return null;
}

function SmoothPanAmbulance({ lat, lng }: { lat?: number; lng?: number }) {
  const map = useMap();
  const lastPos = useRef<[number, number] | null>(null);

  useEffect(() => {
    if (lat !== undefined && lng !== undefined && !isNaN(lat) && !isNaN(lng)) {
      if (!lastPos.current || Math.abs(lastPos.current[0] - lat) > 0.0001 || Math.abs(lastPos.current[1] - lng) > 0.0001) {
        lastPos.current = [lat, lng];
        map.panTo([lat, lng], { animate: true, duration: 0.6 });
      }
    }
  }, [lat, lng, map]);

  return null;
}

function FitBoundsHandler({ allCoords, triggerFit }: { allCoords: [number, number][]; triggerFit: number }) {
  const map = useMap();
  useEffect(() => {
    if (allCoords.length > 1) {
      try {
        const bounds = L.latLngBounds(allCoords);
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15, animate: true });
      } catch {
        // Fallback silently if bounds invalid
      }
    }
  }, [triggerFit, map]);
  return null;
}

// ============================================================================
// MAIN INTERACTIVE TACTICAL MAP COMPONENT
// ============================================================================

export function Map({
  points = [],
  routes = [],
  ambulance = null,
  incident = null,
  ambulances = [],
  incidents = [],
  hospitals = [],
  trail = [],
  onLocationSelect,
  onSelectIncident,
  onSelectAmbulance,
  onSelectHospital,
  selectedIncidentId = null,
  selectedAmbulanceId = null,
  interactive = true,
  simulationMode = false,
  showControls = true,
  height = "100%",
}: MapProps) {
  // Layer visibility toggles
  const [showIncidentsLayer, setShowIncidentsLayer] = useState(true);
  const [showAmbulancesLayer, setShowAmbulancesLayer] = useState(true);
  const [showHospitalsLayer, setShowHospitalsLayer] = useState(true);
  const [showRoutesLayer, setShowRoutesLayer] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [fitTrigger, setFitTrigger] = useState(0);

  // Normalize single and multi item props
  const allIncidents: IncidentMarkerProps[] = useMemo(() => {
    const list = [...incidents];
    if (incident && incident.latitude && incident.longitude && !list.find((x) => x.id === incident.id)) {
      list.push(incident);
    }
    return list.filter((i) => !isNaN(Number(i.latitude)) && !isNaN(Number(i.longitude)));
  }, [incidents, incident]);

  const allAmbulances: AmbulanceMarkerProps[] = useMemo(() => {
    const list = [...ambulances];
    if (ambulance && ambulance.latitude && ambulance.longitude && !list.find((x) => x.id === ambulance.id)) {
      list.push(ambulance);
    }
    return list.filter((a) => !isNaN(Number(a.latitude)) && !isNaN(Number(a.longitude)));
  }, [ambulances, ambulance]);

  const allHospitalsList: HospitalMarkerProps[] = useMemo(() => {
    return hospitals.filter((h) => !isNaN(Number(h.latitude)) && !isNaN(Number(h.longitude)));
  }, [hospitals]);

  const validPoints = useMemo(() => {
    return (points || [])
      .map((p) => {
        const lat = Number(p.latitude);
        const lng = Number(p.longitude);
        const isValid = !isNaN(lat) && !isNaN(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
        return { ...p, lat, lng, isValid };
      })
      .filter((p) => p.isValid);
  }, [points]);

  // Compute bounding coordinates
  const allCoords: [number, number][] = useMemo(() => {
    const coords: [number, number][] = [];
    allIncidents.forEach((i) => coords.push([Number(i.latitude), Number(i.longitude)]));
    allAmbulances.forEach((a) => coords.push([Number(a.latitude), Number(a.longitude)]));
    allHospitalsList.forEach((h) => coords.push([Number(h.latitude), Number(h.longitude)]));
    validPoints.forEach((p) => coords.push([p.lat, p.lng]));
    (routes || []).forEach((r) => {
      if (Array.isArray(r.coordinates)) {
        r.coordinates.forEach((c) => {
          if (Array.isArray(c) && c.length >= 2 && !isNaN(c[0]) && !isNaN(c[1])) {
            coords.push([c[0], c[1]]);
          }
        });
      }
    });
    return coords;
  }, [allIncidents, allAmbulances, allHospitalsList, validPoints, routes]);

  const centerLat = allCoords.length > 0 ? allCoords[0][0] : 13.6288;
  const centerLng = allCoords.length > 0 ? allCoords[0][1] : 79.4192;

  // Filtered incidents by severity
  const filteredIncidents = useMemo(() => {
    if (severityFilter === "all") return allIncidents;
    return allIncidents.filter((i) => (i.priority || "").toLowerCase() === severityFilter);
  }, [allIncidents, severityFilter]);

  // Safely parse polyline coordinates in case strings are provided
  const parsedRoutes = useMemo(() => {
    return (routes || []).map((r) => {
      let coords: [number, number][] = [];
      if (typeof r.coordinates === "string") {
        try {
          coords = JSON.parse(r.coordinates);
        } catch {
          coords = [];
        }
      } else if (Array.isArray(r.coordinates)) {
        coords = r.coordinates.filter((c) => Array.isArray(c) && c.length >= 2 && !isNaN(c[0]) && !isNaN(c[1]));
      }

      let completed: [number, number][] = [];
      if (r.completedCoordinates && Array.isArray(r.completedCoordinates)) {
        completed = r.completedCoordinates.filter((c) => Array.isArray(c) && c.length >= 2 && !isNaN(c[0]) && !isNaN(c[1]));
      }

      return {
        ...r,
        coordinates: coords,
        completedCoordinates: completed,
      };
    });
  }, [routes]);

  return (
    <div
      className="tera-map-container"
      style={{
        position: "relative",
        width: "100%",
        height: height || "100%",
        minHeight: "420px",
      }}
    >
      {/* Simulation Mode Indicator */}
      {simulationMode && (
        <div className="demo-simulation-banner">
          <span>⚡ DEMO SIMULATION MODE</span>
        </div>
      )}

      {/* Floating Tactical Map Controls */}
      {showControls && (
        <div
          style={{
            position: "absolute",
            top: "10px",
            right: "10px",
            zIndex: 1000,
            background: "rgba(15, 23, 42, 0.90)",
            padding: "8px 12px",
            borderRadius: "8px",
            border: "1px solid #334155",
            color: "#f8fafc",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "11px",
            backdropFilter: "blur(6px)",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.4)",
            flexWrap: "wrap",
          }}
        >
          <label style={{ display: "inline-flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showIncidentsLayer}
              onChange={(e) => setShowIncidentsLayer(e.target.checked)}
            />
            🚨 Incidents ({allIncidents.length})
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showAmbulancesLayer}
              onChange={(e) => setShowAmbulancesLayer(e.target.checked)}
            />
            🚑 Ambulances ({allAmbulances.length})
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showHospitalsLayer}
              onChange={(e) => setShowHospitalsLayer(e.target.checked)}
            />
            🏥 Hospitals ({allHospitalsList.length})
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showRoutesLayer}
              onChange={(e) => setShowRoutesLayer(e.target.checked)}
            />
            🛣️ Routes
          </label>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{
              background: "#1e293b",
              color: "#f8fafc",
              border: "1px solid #475569",
              borderRadius: "4px",
              padding: "2px 6px",
              fontSize: "11px",
            }}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical Only</option>
            <option value="high">High Only</option>
            <option value="medium">Medium Only</option>
          </select>

          <button
            type="button"
            onClick={() => setFitTrigger((prev) => prev + 1)}
            style={{
              background: "#0284c7",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              padding: "3px 8px",
              fontWeight: 700,
              cursor: "pointer",
              fontSize: "11px",
            }}
          >
            🎯 Fit All
          </button>
        </div>
      )}

      {/* Main Leaflet Map View */}
      <MapContainer
        center={[centerLat, centerLng]}
        zoom={13}
        className="map"
        style={{ width: "100%", height: "100%", minHeight: "420px" }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />

        <InvalidateSizeHandler />
        {interactive && <ClickHandler onLocationSelect={onLocationSelect} />}
        <FitBoundsHandler allCoords={allCoords} triggerFit={fitTrigger} />

        {/* Follow active ambulance smoothly when available */}
        {ambulance && ambulance.latitude && ambulance.longitude && (
          <SmoothPanAmbulance lat={ambulance.latitude} lng={ambulance.longitude} />
        )}

        {/* 1. Routes and Polylines */}
        {showRoutesLayer &&
          parsedRoutes.map((r, i) => {
            return (
              <div key={`route-wrapper-${i}`}>
                {/* Completed portion of route (Swiggy-style trailing line) */}
                {r.completedCoordinates && r.completedCoordinates.length > 1 && (
                  <Polyline
                    positions={r.completedCoordinates}
                    pathOptions={{
                      color: "#64748b",
                      weight: 4,
                      opacity: 0.6,
                      dashArray: "6, 8",
                    }}
                  />
                )}

                {/* Remaining active route segment */}
                {r.coordinates && r.coordinates.length > 1 && (
                  <Polyline
                    positions={r.coordinates}
                    pathOptions={{
                      color: r.color || "#0284c7",
                      weight: r.weight || 5,
                      opacity: r.opacity || 0.85,
                      dashArray: r.dashArray,
                    }}
                  >
                    {r.label && (
                      <Popup>
                        <strong style={{ fontSize: "12px", color: "#38bdf8" }}>🛣️ {r.label}</strong>
                      </Popup>
                    )}
                  </Polyline>
                )}
              </div>
            );
          })}

        {/* 2. Historical GPS Breadcrumb Trail */}
        {trail && trail.length > 1 && (
          <Polyline
            positions={trail}
            pathOptions={{
              color: "#94a3b8",
              weight: 3,
              opacity: 0.5,
              dashArray: "3, 6",
            }}
          />
        )}

        {/* 3. Hospital Markers */}
        {showHospitalsLayer &&
          allHospitalsList.map((h, i) => {
            const isSel = h.id === selectedIncidentId;
            const availICU = h.available_beds?.icu ?? h.icu_beds ?? 0;
            const availER = h.available_beds?.emergency ?? h.emergency_beds ?? 0;
            const totalAvail = h.available_beds?.total ?? (availICU + availER);

            return (
              <Marker
                key={`hosp-${h.id || i}`}
                position={[Number(h.latitude), Number(h.longitude)]}
                icon={createHospitalMarkerIcon(h, isSel)}
                eventHandlers={{
                  click: () => onSelectHospital && onSelectHospital(h),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "180px" }}>
                    <div style={{ fontWeight: 800, fontSize: "13px", color: "#38bdf8", marginBottom: "4px" }}>
                      🏥 {h.name}
                    </div>
                    {h.hospital_type && (
                      <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "6px" }}>{h.hospital_type}</div>
                    )}
                    <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
                      <span style={{ background: "#0284c7", color: "#fff", padding: "2px 6px", borderRadius: "4px", fontSize: "11px", fontWeight: 700 }}>
                        {availICU} ICU
                      </span>
                      <span style={{ background: "#10b981", color: "#fff", padding: "2px 6px", borderRadius: "4px", fontSize: "11px", fontWeight: 700 }}>
                        {availER} Emergency
                      </span>
                      <span style={{ background: "#334155", color: "#cbd5e1", padding: "2px 6px", borderRadius: "4px", fontSize: "11px" }}>
                        {totalAvail} Total Beds
                      </span>
                    </div>
                    {h.diversion_status && (
                      <div style={{ background: "rgba(239, 68, 68, 0.2)", color: "#ef4444", padding: "3px 6px", borderRadius: "4px", fontSize: "10px", fontWeight: 700, marginBottom: "4px" }}>
                        ⚠️ DIVERSION ACTIVE: No new referrals accepted
                      </div>
                    )}
                    {h.emergency_phone && (
                      <div style={{ fontSize: "11px", color: "#cbd5e1" }}>
                        📞 Emergency: <strong>{h.emergency_phone}</strong>
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}

        {/* 4. Active Emergency Incident Markers */}
        {showIncidentsLayer &&
          filteredIncidents.map((inc, i) => {
            const isSel = inc.id === selectedIncidentId;
            return (
              <Marker
                key={`inc-${inc.id || inc.case_id || i}`}
                position={[Number(inc.latitude), Number(inc.longitude)]}
                icon={createEmergencyMarkerIcon(inc, isSel)}
                eventHandlers={{
                  click: () => onSelectIncident && onSelectIncident(inc),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "190px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
                      <strong style={{ fontSize: "13px", color: "#f87171" }}>
                        🚨 {inc.case_id || "Emergency Incident"}
                      </strong>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 800,
                          textTransform: "uppercase",
                          padding: "1px 6px",
                          borderRadius: "4px",
                          background: (inc.priority || "") === "critical" ? "#ef4444" : "#f59e0b",
                          color: "#ffffff",
                        }}
                      >
                        {inc.priority || "unassessed"}
                      </span>
                    </div>
                    <div style={{ fontSize: "12px", color: "#cbd5e1", marginBottom: "4px" }}>
                      Category: <strong>{(inc.category || "emergency").replace(/_/g, " ")}</strong>
                    </div>
                    <div style={{ fontSize: "12px", color: "#cbd5e1", marginBottom: "4px" }}>
                      Casualties: <strong>{inc.casualties_count || 1} patient(s)</strong>
                    </div>
                    {inc.address && (
                      <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px", lineHeight: 1.3 }}>
                        📍 {inc.address}
                      </div>
                    )}
                    {onSelectIncident && (
                      <button
                        type="button"
                        onClick={() => onSelectIncident(inc)}
                        style={{
                          marginTop: "8px",
                          width: "100%",
                          background: "#ef4444",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "4px",
                          padding: "4px 8px",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        Focus Incident & Triage
                      </button>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}

        {/* 5. Live Ambulance Fleet Markers */}
        {showAmbulancesLayer &&
          allAmbulances.map((amb, i) => {
            const isSel = amb.id === selectedAmbulanceId;
            return (
              <Marker
                key={`amb-${amb.id || amb.registration || i}`}
                position={[Number(amb.latitude), Number(amb.longitude)]}
                icon={createAmbulanceMarkerIcon(amb, isSel)}
                eventHandlers={{
                  click: () => onSelectAmbulance && onSelectAmbulance(amb),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "180px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
                      <strong style={{ fontSize: "13px", color: "#38bdf8" }}>
                        🚑 {amb.registration || "Ambulance Unit"}
                      </strong>
                      <span style={{ fontSize: "10px", fontWeight: 700, textTransform: "uppercase", color: "#10b981" }}>
                        {amb.status || "Ready"}
                      </span>
                    </div>
                    <div style={{ fontSize: "11px", color: "#cbd5e1", marginBottom: "2px" }}>
                      Type: <strong>{amb.vehicleType || "Advanced Life Support (ALS)"}</strong>
                    </div>
                    {amb.patientCapacity && (
                      <div style={{ fontSize: "11px", color: "#cbd5e1", marginBottom: "2px" }}>
                        Capacity: <strong>{amb.patientCapacity} patient(s)</strong>
                      </div>
                    )}
                    {amb.driverName && (
                      <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
                        Pilot: <strong>{amb.driverName}</strong>
                      </div>
                    )}
                    {amb.driverPhone && (
                      <a
                        href={`tel:${amb.driverPhone.replace(/[\s-]/g, "")}`}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          background: "#10b981",
                          color: "#ffffff",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          textDecoration: "none",
                          fontSize: "11px",
                          fontWeight: 700,
                          marginTop: "4px",
                        }}
                      >
                        📞 Call {amb.driverPhone}
                      </a>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}

        {/* 6. Legacy Generic Points (Backwards Compatibility) */}
        {validPoints.map((p, i) => (
          <CircleMarker
            key={`point-${i}`}
            center={[p.lat, p.lng]}
            radius={8}
            pathOptions={{ color: "#0284c7", fillColor: "#38bdf8", fillOpacity: 0.9, weight: 2 }}
          >
            <Popup>
              <strong>{p.name || "Location Pin"}</strong>
              {p.detail && (
                <>
                  <br />
                  <span style={{ fontSize: "11px", color: "#cbd5e1" }}>{p.detail}</span>
                </>
              )}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Map Hint Footer */}
      {interactive && onLocationSelect && (
        <div
          style={{
            position: "absolute",
            bottom: "8px",
            left: "8px",
            background: "rgba(15, 23, 42, 0.85)",
            color: "#f8fafc",
            padding: "4px 8px",
            borderRadius: "6px",
            fontSize: "11px",
            zIndex: 1000,
            pointerEvents: "none",
            border: "1px solid #334155",
          }}
        >
          📍 Click anywhere on map to drop emergency pin
        </div>
      )}
    </div>
  );
}
