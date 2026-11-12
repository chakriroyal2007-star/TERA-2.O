import { useState, useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowUpRight,
  MapPin,
  ShieldCheck,
  Radio,
  Activity,
  HeartPulse,
  Truck,
  ChartNoAxesCombined,
  Users,
  LocateFixed,
  CheckCircle2,
  ArrowRight,
  Flame,
  AlertTriangle,
  ShieldAlert,
  Download,
  Upload,
  X,
  FileText,
  Navigation,
  Database,
  User,
  Phone,
} from "lucide-react";
import { api, apiUrl, queryClient, date, label } from "./api";
import {
  PageHead,
  ErrorBox,
  Badge,
  Panel,
  DataForm,
  Loading,
} from "./components";
import { Map } from "./Map";
import { VoiceReporter } from "./VoiceRecorder";
import { EmergencyCompanion } from "./EmergencyCompanion";

export function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark">
        <Activity size={22} />
      </span>
      <span>
        tera<span className="brand-dot">.</span>
      </span>
    </Link>
  );
}

export function PublicNav() {
  return (
    <nav className="public-nav" aria-label="Public navigation">
      <Brand />
      <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", flexWrap: "wrap" }}>
        <Link to="/report">Report an emergency</Link>
        <Link to="/track">Track a report</Link>
        <Link
          to="/dbms"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
            fontWeight: 700,
            color: "#34d399",
            background: "rgba(16, 185, 129, 0.14)",
            border: "1px solid rgba(16, 185, 129, 0.35)",
            padding: "0.35rem 0.85rem",
            borderRadius: "9999px",
            textDecoration: "none",
            boxShadow: "0 0 10px rgba(16, 185, 129, 0.15)",
          }}
        >
          <Database size={15} /> DBMS Studio
        </Link>
        <Link className="secondary" to="/login">
          Team sign in <ArrowUpRight size={16} />
        </Link>
      </div>
    </nav>
  );
}

export function Landing() {
  const nav = useNavigate();
  const [launchingRole, setLaunchingRole] = useState<string | null>(null);

  const handleRoleLaunch = async (r: any) => {
    setLaunchingRole(r.roleKey);
    try {
      const user = await api<any>("/auth/login", "POST", {
        email: r.email,
        password: "Emergency@2025!",
        mfa_code: null,
      });
      queryClient.setQueryData(["me"], user);
      nav(r.dest);
    } catch {
      nav(`/login?role=${r.roleKey.toLowerCase()}`);
    } finally {
      setLaunchingRole(null);
    }
  };
  const categories = [
    {
      id: "medical",
      name: "Medical Emergency",
      desc: "Cardiac arrest, severe trauma, unconsciousness, stroke",
      icon: HeartPulse,
      color: "#ef4444",
    },
    {
      id: "road_collision",
      name: "Road Collision",
      desc: "Vehicle crashes, pile-ups, pedestrian collisions, trapped victims",
      icon: Truck,
      color: "#f97316",
    },
    {
      id: "fire",
      name: "Fire Outbreak",
      desc: "Structure fires, industrial blaze, chemical fire, smoke inhalation",
      icon: Flame,
      color: "#eab308",
    },
    {
      id: "disaster",
      name: "Structural Collapse / Disaster",
      desc: "Building collapse, floods, earthquakes, landslides, storm impact",
      icon: AlertTriangle,
      color: "#8b5cf6",
    },
    {
      id: "hazardous",
      name: "Hazardous Condition",
      desc: "Gas leaks, downed power lines, toxic spills, structural risks",
      icon: ShieldAlert,
      color: "#06b6d4",
    },
    {
      id: "other",
      name: "Other Emergency",
      desc: "Public safety hazards, missing persons, water emergencies",
      icon: Activity,
      color: "#10b981",
    },
  ];

  const roles = [
    {
      icon: Radio,
      name: "Control Operators",
      roleKey: "Operator",
      email: "operator@tera.org",
      dest: "/app",
      text: "Verify voice and text reports. Coordinate resources. Monitor dispatches.",
    },
    {
      icon: HeartPulse,
      name: "Hospital Coordinators",
      roleKey: "Hospital",
      email: "hospital@tera.org",
      dest: "/app/hospitals",
      text: "Keep department bed capacities current and prepare for incoming arrivals.",
    },
    {
      icon: Truck,
      name: "Field Responders",
      roleKey: "Responder",
      email: "responder@tera.org",
      dest: "/app/missions",
      text: "Receive mission assignments, update en-route status, and complete handovers.",
    },
    {
      icon: ChartNoAxesCombined,
      name: "Operational Analysts",
      roleKey: "Analyst",
      email: "analyst@tera.org",
      dest: "/app/analytics",
      text: "Audit response times, verify dispatch SLAs, and inspect performance trends.",
    },
    {
      icon: Users,
      name: "System Administrators",
      roleKey: "Admin",
      email: "admin@tera.org",
      dest: "/app",
      text: "Manage team credentials, hospital facilities, ambulances, and RBAC policies.",
    },
  ];

  return (
    <>
      <PublicNav />
      <main className="landing">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow light">
              <span className="tiny-line" /> Temporal Emergency Resource Allocation & Coordination Platform
            </div>
            <h1>
              Every second
              <br />
              needs a <em>response.</em>
            </h1>
            <p>
              From citizen voice report to hospital handover. TERA unites public callers,
              dispatch operators, rescue units, and emergency departments into one coordinated workflow.
            </p>
            <div className="hero-actions">
              <Link className="primary bright" to="/report">
                Start Emergency Report <ArrowUpRight size={19} />
              </Link>
              <Link className="text-link" to="/track">
                Track a Report <ArrowRight size={17} />
              </Link>
              <Link
                to="/dbms"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.65rem 1.25rem",
                  background: "rgba(16, 185, 129, 0.15)",
                  border: "1px solid rgba(16, 185, 129, 0.4)",
                  borderRadius: "8px",
                  color: "#34d399",
                  fontWeight: 700,
                  fontSize: "0.95rem",
                  textDecoration: "none",
                  transition: "all 0.2s ease",
                  boxShadow: "0 0 15px rgba(16, 185, 129, 0.15)",
                }}
              >
                <Database size={18} /> DBMS Studio ⚡
              </Link>
            </div>
            <div className="hero-note">
              <ShieldCheck size={17} /> No account needed to report. Free public emergency coordination.
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Emergency coordination lifecycle"
          >
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit orbit-three" />
            <div className="visual-core">
              <Activity size={42} />
              <span>TERA</span>
              <small>LIVE RESPONSE</small>
            </div>
            <div className="orbit-card card-report">
              <span>01</span>
              <MapPin />
              <div>
                Report<small>Multilingual Voice & GPS</small>
              </div>
            </div>
            <div className="orbit-card card-dispatch">
              <span>02</span>
              <Radio />
              <div>
                Coordinate<small>Operator Dispatch Desk</small>
              </div>
            </div>
            <div className="orbit-card card-care">
              <span>03</span>
              <HeartPulse />
              <div>
                Care<small>Hospital Bed Handover</small>
              </div>
            </div>
          </div>
        </section>

        {/* 6 Supported Emergency Categories */}
        <section className="how" style={{ paddingTop: "2rem" }}>
          <div>
            <div className="eyebrow">Public Safety Dispatch</div>
            <h2>Supported Emergency Categories</h2>
          </div>
          <p>
            Citizens can report any critical situation using voice or the manual form.
            AI automatically extracts casualty numbers, location landmarks, and requested resources.
          </p>
        </section>

        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "1.25rem",
            maxWidth: "1200px",
            margin: "0 auto 3rem auto",
            padding: "0 1.5rem",
          }}
        >
          {categories.map((c) => (
            <Link
              to="/report"
              key={c.id}
              style={{
                background: "rgba(15, 23, 42, 0.75)",
                border: "1px solid rgba(51, 65, 85, 0.8)",
                borderRadius: "12px",
                padding: "1.5rem",
                color: "#f8fafc",
                textDecoration: "none",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = c.color;
                e.currentTarget.style.transform = "translateY(-3px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(51, 65, 85, 0.8)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              <div
                style={{
                  width: "42px",
                  height: "42px",
                  borderRadius: "8px",
                  background: `${c.color}20`,
                  color: c.color,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <c.icon size={22} />
              </div>
              <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{c.name}</h3>
              <p style={{ margin: 0, fontSize: "0.875rem", color: "#94a3b8", lineHeight: 1.5 }}>
                {c.desc}
              </p>
              <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: "0.25rem", color: c.color, fontSize: "0.85rem", fontWeight: 600 }}>
                Report this emergency <ArrowUpRight size={14} />
              </div>
            </Link>
          ))}
        </section>

        {/* Operational Staff Access Distinction */}
        <section className="how">
          <div>
            <div className="eyebrow">Authorized Operations</div>
            <h2>Operational Access & Role Workflows</h2>
          </div>
          <p>
            Emergency responders, hospital triage coordinators, and dispatch operators require authenticated credentials to access live operational tools.
          </p>
        </section>

        <section className="role-grid">
          {roles.map((r) => (
            <div
              className="role-card"
              key={r.name}
              onClick={() => handleRoleLaunch(r)}
              style={{ cursor: "pointer", position: "relative" }}
            >
              <r.icon />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>{r.name}</h3>
                <span style={{ fontSize: "0.72rem", background: "rgba(16, 185, 129, 0.15)", color: "#10b981", padding: "2px 6px", borderRadius: "4px", fontWeight: 700 }}>
                  {launchingRole === r.roleKey ? "Launching…" : `Launch ${r.roleKey} Desk →`}
                </span>
              </div>
              <p>{r.text}</p>
              <ArrowUpRight className="role-arrow" size={18} />
            </div>
          ))}
        </section>

        <div className="deployment-note">
          TERA Platform · Emergency reports are queued immediately in PostgreSQL and dispatched to active operators.
        </div>
      </main>
      <footer>
        <Brand />
        <span>Temporal Emergency Resource Allocation & Coordination</span>
        <Link to="/report">
          Start a Report <ArrowUpRight size={14} />
        </Link>
      </footer>
    </>
  );
}

const reportSchema = z
  .object({
    category: z.enum([
      "medical",
      "road_collision",
      "fire",
      "disaster",
      "other",
    ]),
    description: z
      .string()
      .min(10, "Describe the situation in at least 10 characters")
      .max(5000),
    address: z.string().min(3, "Enter a location or landmark").max(500),
    latitude: z.union([
      z.literal(""),
      z.coerce.number<string | number>().min(-90).max(90),
    ]),
    longitude: z.union([
      z.literal(""),
      z.coerce.number<string | number>().min(-180).max(180),
    ]),
    casualties_count: z.union([z.literal(""), z.coerce.number().min(0)]).optional(),
    severity: z.enum(["low", "medium", "high", "critical"]).optional(),
    reporter_name: z.string().max(100).optional(),
    reporter_phone: z.string().max(30).optional(),
  })
  .refine((v) => (v.latitude === "") === (v.longitude === ""), {
    message: "Enter both coordinates",
    path: ["longitude"],
  });

type ReportValues = z.infer<typeof reportSchema>;

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
      { headers: { "Accept-Language": "en" } }
    );
    if (res.ok) {
      const data = await res.json();
      if (data.display_name) {
        const parts = data.display_name.split(", ");
        return parts.slice(0, 3).join(", ");
      }
    }
  } catch {
    // ignore
  }
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

export function ReportPage() {
  const nav = useNavigate();
  const [reportMode, setReportMode] = useState<"voice" | "text">("text");
  const [geoWarning, setGeoWarning] = useState<string>("");
  const [geoBusy, setGeoBusy] = useState(false);
  const [address, setAddress] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [evidenceList, setEvidenceList] = useState<{ id: string; name: string; previewUrl: string }[]>([]);
  const [evidenceBusy, setEvidenceBusy] = useState(false);

  // Post-submission state
  const [submittedIncident, setSubmittedIncident] = useState<{
    id: string;
    case_id: string;
    tracking_code: string;
    pdf_url: string;
    category: string;
    address: string;
  } | null>(null);

  const [companionOpen, setCompanionOpen] = useState(false);

  const form = useForm<z.input<typeof reportSchema>, unknown, ReportValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: {
      category: "medical",
      description: "",
      address: "",
      latitude: "",
      longitude: "",
      severity: "medium",
      reporter_name: "",
      reporter_phone: "",
    },
  });

  const m = useMutation({
    mutationFn: async (v: ReportValues) => {
      const citizenContact =
        v.reporter_name && v.reporter_phone
          ? `${v.reporter_name} (Phone: ${v.reporter_phone})`
          : v.reporter_phone
            ? `Phone: ${v.reporter_phone}`
            : v.reporter_name || null;

        return await api<{
          id: string;
          case_id: string;
          tracking_code: string;
          status: string;
          pdf_url: string;
        }>("/incidents", "POST", {
          category: v.category,
          description: v.description,
          address: v.address,
          latitude: v.latitude === "" ? null : Number(v.latitude),
          longitude: v.longitude === "" ? null : Number(v.longitude),
          casualties_count: v.casualties_count ? Number(v.casualties_count) : null,
          severity: v.severity || "medium",
          citizen_contact: citizenContact,
          evidence_ids: evidenceList.map((e) => e.id),
        });

    },
    onSuccess: (r, v) => {
      setSubmittedIncident({
        id: r.id,
        case_id: r.case_id,
        tracking_code: r.tracking_code,
        pdf_url: r.pdf_url,
        category: v.category,
        address: v.address,
      });
    },
  });

  // Keep form lat/lng in sync with component state
  useEffect(() => {
    form.setValue("latitude", latitude as any);
    form.setValue("longitude", longitude as any);
  }, [latitude, longitude]);

  useEffect(() => {
    form.setValue("address", address);
  }, [address]);

  // Handle map clicks
  async function handleMapLocationSelect(lat: number, lng: number) {
    setLatitude(lat.toFixed(6));
    setLongitude(lng.toFixed(6));
    setGeoWarning("");
    const rev = await reverseGeocode(lat, lng);
    if (rev) {
      setAddress(rev);
    }
  }

  function locate() {
    setGeoBusy(true);
    setGeoWarning("");
    if (!navigator.geolocation) {
      setGeoBusy(false);
      setGeoWarning("Geolocation is not supported by your browser. You can enter an address or click on the map to set a pin.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        const latStr = p.coords.latitude.toFixed(6);
        const lngStr = p.coords.longitude.toFixed(6);
        setLatitude(latStr);
        setLongitude(lngStr);
        setGeoBusy(false);
        const rev = await reverseGeocode(p.coords.latitude, p.coords.longitude);
        if (rev) {
          setAddress(rev);
        }
      },
      (e) => {
        setGeoBusy(false);
        // Friendly notice - NEVER block reporting
        setGeoWarning("📍 Location permission was not granted by your browser. You can type your location manually or click anywhere on the map to place an emergency marker. Report submission is never blocked.");
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  async function handleEvidenceUpload(files: FileList | null) {
    if (!files || !files.length) return;
    setEvidenceBusy(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fd = new FormData();
        fd.append("file", file);
        const res = await api<{ id: string; object_key: string }>("/public/evidence", "POST", fd);
        const previewUrl = URL.createObjectURL(file);
        setEvidenceList((prev) => [...prev, { id: res.id, name: file.name, previewUrl }]);
      }
    } catch (e: any) {
      setGeoWarning(e.message || "Failed to upload photo evidence.");
    } finally {
      setEvidenceBusy(false);
    }
  }

  function removeEvidence(id: string) {
    setEvidenceList((prev) => {
      const target = prev.find((e) => e.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((e) => e.id !== id);
    });
  }

  // If incident was submitted, render Confirmation Screen
  if (submittedIncident) {
    return (
      <>
        <PublicNav />
        <main className="public-content narrow">
          <div
            style={{
              background: "rgba(15, 23, 42, 0.9)",
              border: "1px solid #10b981",
              borderRadius: "16px",
              padding: "2.5rem 2rem",
              textAlign: "center",
              color: "#f8fafc",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
              marginTop: "2rem",
            }}
          >
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "50%",
                background: "rgba(16, 185, 129, 0.15)",
                color: "#10b981",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 1.5rem auto",
              }}
            >
              <CheckCircle2 size={36} />
            </div>

            <h1 style={{ fontSize: "1.75rem", marginBottom: "0.5rem" }}>
              Emergency Report Submitted Successfully
            </h1>
            <p style={{ color: "#94a3b8", fontSize: "1rem", maxWidth: "540px", margin: "0 auto 1.5rem auto" }}>
              Your report has been saved in the dispatch queue. Submission does not confirm a responder assignment. Call 112 for emergency help.
            </p>

            <div
              style={{
                background: "rgba(30, 41, 59, 0.7)",
                border: "1px solid #334155",
                borderRadius: "10px",
                padding: "1.25rem",
                display: "inline-block",
                marginBottom: "2rem",
                textAlign: "left",
                minWidth: "320px",
              }}
            >
              <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "0.25rem" }}>
                Official Case ID:
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#38bdf8", letterSpacing: "1px" }}>
                {submittedIncident.case_id}
              </div>
              <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginTop: "0.75rem", marginBottom: "0.25rem" }}>
                Private Tracking Code:
              </div>
              <code style={{ fontSize: "1rem", color: "#f8fafc", background: "#0f172a", padding: "2px 8px", borderRadius: "4px" }}>
                {submittedIncident.tracking_code}
              </code>
            </div>

            {/* AI Emergency First-Aid Companion Action Card */}
            <div
              style={{
                background: "linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(30, 27, 75, 0.5) 100%)",
                border: "2px solid #ef4444",
                borderRadius: "14px",
                padding: "1.5rem",
                maxWidth: "600px",
                margin: "0 auto 2rem auto",
                textAlign: "left",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
                <HeartPulse size={26} color="#ef4444" />
                <h3 style={{ margin: 0, fontSize: "1.2rem", color: "#ffffff" }}>
                  AI Emergency First-Aid Companion
                </h3>
                <span style={{ background: "#ef4444", color: "#fff", fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px" }}>
                  RECOMMENDED
                </span>
              </div>
              <p style={{ color: "#cbd5e1", fontSize: "0.95rem", lineHeight: "1.5", margin: "0 0 1rem 0" }}>
                Ask questions in <strong>Telugu, Hindi, English, Tamil, Kannada, or Malayalam</strong> and save updates with your case. Source-based safety guidance is available in English.
              </p>
              <button
                type="button"
                onClick={() => setCompanionOpen(true)}
                style={{
                  background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
                  color: "#ffffff",
                  border: "none",
                  padding: "0.85rem 1.5rem",
                  fontSize: "1rem",
                  fontWeight: 700,
                  borderRadius: "8px",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  width: "100%",
                  justifyContent: "center",
                }}
              >
                <HeartPulse size={18} /> Launch AI First-Aid Companion
              </button>
            </div>

            {/* Companion Modal */}
            {companionOpen && (
              <div
                style={{
                  position: "fixed",
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: "rgba(0, 0, 0, 0.85)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 2000,
                  padding: "1rem",
                }}
              >
                <div style={{ maxWidth: "900px", width: "100%" }}>
                  <EmergencyCompanion
                    incidentId={submittedIncident.id}
                    trackingCode={submittedIncident.tracking_code}
                    initialCategory={submittedIncident.category}
                    onClose={() => setCompanionOpen(false)}
                  />
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap", marginBottom: "1.5rem" }}>
              <a
                href={
                  submittedIncident.pdf_url && submittedIncident.pdf_url !== "#"
                    ? apiUrl(submittedIncident.pdf_url)
                    : "#"
                }
                onClick={(e) => {
                  if (!submittedIncident.pdf_url || submittedIncident.pdf_url === "#") {
                    e.preventDefault();
                    window.print();
                  }
                }}
                target="_blank"
                rel="noopener noreferrer"
                className="primary bright"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  textDecoration: "none",
                  padding: "0.85rem 1.5rem",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "1rem",
                }}
              >
                <Download size={18} /> Download Official PDF Report
              </a>
              <Link
                to={`/track/${submittedIncident.tracking_code}`}
                className="secondary"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  textDecoration: "none",
                  padding: "0.85rem 1.5rem",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "1rem",
                }}
              >
                <Navigation size={18} /> Track My Incident Status
              </Link>
            </div>

            <div>
              <button
                type="button"
                onClick={() => {
                  setSubmittedIncident(null);
                  form.reset();
                  setAddress("");
                  setLatitude("");
                  setLongitude("");
                  setEvidenceList([]);
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                  textDecoration: "underline",
                }}
              >
                Submit another report
              </button>
            </div>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <PublicNav />
      <main className="public-content">
        <PageHead
          eyebrow="TERA Emergency Assistance"
          title="Report an emergency."
        >
          Speak in your language or enter details below. After you submit, launch the AI Companion with your saved incident details.
        </PageHead>

        {/* National Emergency Hotline Direct Call Guidance */}
        <div
          style={{
            background: "linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(185, 28, 28, 0.08) 100%)",
            border: "1px solid rgba(239, 68, 68, 0.35)",
            borderRadius: "10px",
            padding: "0.85rem 1.25rem",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.4rem" }}>🚨</span>
            <div>
              <strong style={{ color: "#f87171", fontSize: "0.95rem", display: "block" }}>
                Immediate Life-Threatening Situation?
              </strong>
              <span style={{ color: "#cbd5e1", fontSize: "0.82rem" }}>
                Contact national emergency authorities immediately. Every second counts.
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <a
              href="tel:112"
              style={{
                background: "#dc2626",
                color: "#ffffff",
                padding: "8px 14px",
                borderRadius: "6px",
                textDecoration: "none",
                fontWeight: 700,
                fontSize: "0.85rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 2px 8px rgba(220, 38, 38, 0.4)",
              }}
            >
              📞 Call 112 (National)
            </a>
            <a
              href="tel:108"
              style={{
                background: "#b91c1c",
                color: "#ffffff",
                padding: "8px 14px",
                borderRadius: "6px",
                textDecoration: "none",
                fontWeight: 700,
                fontSize: "0.85rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 2px 8px rgba(185, 28, 28, 0.4)",
              }}
            >
              🚑 Call 108 (Ambulance)
            </a>
          </div>
        </div>

        <div className="two-col">
          {/* Left Column: Form & Voice Studio */}
          <Panel
            title="Emergency report"
            aside={
              <div className="report-mode-tabs">
                <button
                  type="button"
                  className={reportMode === "voice" ? "active" : ""}
                  onClick={() => setReportMode("voice")}
                >
                  🎙️ Voice Report
                </button>
                <button
                  type="button"
                  className={reportMode === "text" ? "active" : ""}
                  onClick={() => setReportMode("text")}
                >
                  📝 Manual Form
                </button>
              </div>
            }
          >
            {reportMode === "voice" ? (
              <VoiceReporter
                initialAddress={address}
                initialLat={latitude}
                initialLng={longitude}
                onLocationChange={(lat, lng, addr) => {
                  setLatitude(lat);
                  setLongitude(lng);
                  setAddress(addr);
                }}
                onExtractionApplied={(ext, tr) => {
                  if (ext.category) form.setValue("category", ext.category as any);
                  if (tr || ext.description) form.setValue("description", tr || ext.description);
                  if (ext.affected_people != null) form.setValue("casualties_count", Number(ext.affected_people) as any);
                  if (ext.severity) form.setValue("severity", ext.severity as any);
                  if (ext.location_text && ext.location_text !== "Location described in voice report") {
                    setAddress(ext.location_text);
                    form.setValue("address", ext.location_text);
                  }
                }}
                onIncidentSubmitted={(res) => setSubmittedIncident(res)}
              />
            ) : (
              <form
                className="data-form"
                onSubmit={form.handleSubmit((v) => m.mutate(v))}
              >
                <div
                  style={{
                    background: "rgba(30, 41, 59, 0.5)",
                    border: "1px dashed #475569",
                    borderRadius: "8px",
                    padding: "0.6rem 0.85rem",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "0.75rem",
                  }}
                >
                  <span style={{ fontSize: "0.85rem", color: "#cbd5e1" }}>
                    🎙️ Prefer speaking? Use AI Voice to auto-fill this form.
                  </span>
                  <button
                    type="button"
                    onClick={() => setReportMode("voice")}
                    style={{
                      background: "#0284c7",
                      color: "#fff",
                      border: "none",
                      padding: "5px 12px",
                      borderRadius: "6px",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    🎙️ Voice Dictation
                  </button>
                </div>

                <label>
                  Emergency Category
                  <select {...form.register("category")}>
                    <option value="medical">Medical emergency</option>
                    <option value="road_collision">Road collision</option>
                    <option value="fire">Fire outbreak</option>
                    <option value="disaster">Structural collapse / Disaster</option>
                    <option value="other">Other emergency</option>
                  </select>
                </label>

                <label>
                  Severity / Priority
                  <select {...form.register("severity")}>
                    <option value="critical">Critical (Life-threatening)</option>
                    <option value="high">High (Urgent care)</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low (Stable)</option>
                  </select>
                </label>

                <label>
                  What is happening?
                  <textarea
                    {...form.register("description")}
                    placeholder="Describe what you see. Mention vehicles involved, number of injured, and immediate hazards."
                    rows={4}
                  />
                </label>

                <label>
                  Address or nearby landmark
                  <input
                    {...form.register("address")}
                    value={address}
                    onChange={(e) => {
                      setAddress(e.target.value);
                      form.setValue("address", e.target.value, { shouldValidate: true });
                    }}
                    placeholder="Street, building, area or landmark (e.g. Near Bus Stand, Tirupati)"
                  />
                </label>

                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", margin: "0.5rem 0" }}>
                  <button
                    type="button"
                    className="secondary"
                    disabled={geoBusy}
                    onClick={locate}
                    style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
                  >
                    <LocateFixed size={16} />
                    {geoBusy ? "Detecting GPS…" : "Use my current GPS"}
                  </button>
                  <small style={{ color: "#94a3b8" }}>Or click on the map to place a pin</small>
                </div>

                {geoWarning && (
                  <div
                    style={{
                      background: "rgba(234, 179, 8, 0.1)",
                      border: "1px solid #eab308",
                      borderRadius: "6px",
                      padding: "0.75rem",
                      fontSize: "0.85rem",
                      color: "#fef08a",
                      margin: "0.5rem 0",
                    }}
                  >
                    {geoWarning}
                  </div>
                )}

                <div className="two-fields">
                  <label>
                    Latitude (optional)
                    <input
                      type="number"
                      step="any"
                      value={latitude}
                      onChange={(e) => {
                        setLatitude(e.target.value);
                        form.setValue("latitude", e.target.value as any);
                      }}
                      placeholder="e.g. 13.6288"
                    />
                  </label>
                  <label>
                    Longitude (optional)
                    <input
                      type="number"
                      step="any"
                      value={longitude}
                      onChange={(e) => {
                        setLongitude(e.target.value);
                        form.setValue("longitude", e.target.value as any);
                      }}
                      placeholder="e.g. 79.4192"
                    />
                  </label>
                </div>

                <label>
                  Approximate Casualties
                  <input
                    type="number"
                    min="0"
                    placeholder="Number of affected or injured people"
                    {...form.register("casualties_count")}
                  />
                </label>

                {/* Caller / Reporter Information */}
                <div className="two-fields" style={{ margin: "0.75rem 0" }}>
                  <label>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", marginBottom: "0.25rem" }}>
                      <User size={14} color="#38bdf8" />
                      <span>Your Name (Caller / Witness)</span>
                    </div>
                    <input
                      type="text"
                      placeholder="e.g. Rahul Sharma"
                      {...form.register("reporter_name")}
                    />
                  </label>

                  <label>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", marginBottom: "0.25rem" }}>
                      <Phone size={14} color="#34d399" />
                      <span>Phone / Contact Number</span>
                    </div>
                    <input
                      type="tel"
                      placeholder="e.g. +91 98765 43210"
                      {...form.register("reporter_phone")}
                    />
                  </label>
                </div>

                {/* Evidence attachments for manual form */}
                <div style={{ margin: "1rem 0" }}>
                  <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.875rem", fontWeight: 600 }}>
                    <span>📸 Attach Photo / Audio Evidence (Optional)</span>
                    {evidenceBusy && <small style={{ color: "#38bdf8" }}>Uploading…</small>}
                  </label>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
                    {evidenceList.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          position: "relative",
                          width: "60px",
                          height: "60px",
                          borderRadius: "6px",
                          overflow: "hidden",
                          border: "1px solid #334155",
                        }}
                      >
                        <img
                          src={item.previewUrl}
                          alt={item.name}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        />
                        <button
                          type="button"
                          onClick={() => removeEvidence(item.id)}
                          style={{
                            position: "absolute",
                            top: 2,
                            right: 2,
                            background: "rgba(0,0,0,0.7)",
                            color: "#fff",
                            border: "none",
                            borderRadius: "50%",
                            width: "16px",
                            height: "16px",
                            cursor: "pointer",
                            padding: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <X size={10} />
                        </button>
                      </div>
                    ))}
                    <label
                      style={{
                        width: "60px",
                        height: "60px",
                        borderRadius: "6px",
                        border: "2px dashed #475569",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        color: "#94a3b8",
                        fontSize: "10px",
                      }}
                    >
                      <Upload size={14} />
                      <span>Add</span>
                      <input
                        type="file"
                        multiple
                        accept="image/jpeg,image/png,image/webp,audio/wav,audio/webm"
                        style={{ display: "none" }}
                        onChange={(e) => handleEvidenceUpload(e.target.files)}
                      />
                    </label>
                  </div>
                </div>

                {Object.values(form.formState.errors).map((e, i) => (
                  <ErrorBox key={i} error={e.message} />
                ))}
                <ErrorBox error={m.error} />

                <button className="primary" disabled={m.isPending} style={{ marginTop: "1rem" }}>
                  {m.isPending ? "Submitting to Dispatch…" : "Submit emergency report"}
                  <ArrowUpRight size={18} />
                </button>
              </form>
            )}
          </Panel>

          {/* Right Column: Interactive Location Map & Status */}
          <div>
            <Panel title="Emergency Location Map">
              <Map
                points={
                  latitude !== "" && longitude !== ""
                    ? [
                        {
                          latitude: Number(latitude),
                          longitude: Number(longitude),
                          name: "Reported Incident Pin",
                          detail: address || "Emergency Location",
                        },
                      ]
                    : []
                }
                onLocationSelect={handleMapLocationSelect}
                interactive={true}
              />
              <div
                style={{
                  background: "rgba(15, 23, 42, 0.6)",
                  borderRadius: "8px",
                  padding: "0.75rem",
                  marginTop: "0.75rem",
                  border: "1px solid #334155",
                  fontSize: "0.85rem",
                  color: "#cbd5e1",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <strong>Selected Coordinates:</strong>
                  <span>
                    {latitude && longitude ? `${Number(latitude).toFixed(4)}, ${Number(longitude).toFixed(4)}` : "None"}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong>Resolved Address:</strong>
                  <span className="truncate" style={{ maxWidth: "220px" }}>
                    {address || "Click map to resolve"}
                  </span>
                </div>
              </div>
            </Panel>

            <div className="info-card" style={{ marginTop: "1rem" }}>
              <ShieldCheck />
              <h3>Your report stays traceable.</h3>
              <p>
                Every submission generates a human-readable case ID and private tracking code.
                Follow response milestones, download your official coordination PDF, and upload updates.
              </p>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}

export function TrackPage() {
  const { code } = useParams();
  const nav = useNavigate();
  const [input, setInput] = useState("");
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [uploaded, setUploaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [companionOpen, setCompanionOpen] = useState(false);

  const q = useQuery({
    queryKey: ["tracking", code],
    queryFn: () => api("/public/track/" + encodeURIComponent(code!)),
    enabled: !!code,
    refetchInterval: 10000,
  });

  return (
    <>
      <PublicNav />
      <main className="public-content narrow">
        <PageHead eyebrow="TERA Citizen Portal" title="Follow your report.">
          Real-time milestones from the dispatch and hospital coordination teams.
        </PageHead>
        <Panel title="Incident Tracking & Verification">
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              nav("/track/" + encodeURIComponent(input.trim()));
            }}
          >
            <label className="grow">
              <span className="sr-only">Private tracking code</span>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Enter TRK-…"
                required
              />
            </label>
            <button className="primary">
              Track <ArrowRight size={16} />
            </button>
          </form>
          {code && (
            <div className="tracking-code">
              <small>Tracking Reference:</small>
              <code>{code}</code>
            </div>
          )}
        </Panel>

        <ErrorBox error={q.error} />
        {q.isLoading && code && <Loading />}

        {q.data && (
          <>
            <Panel
              title="Report Progress & Status"
              aside={
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <button
                    type="button"
                    onClick={() => setCompanionOpen(true)}
                    style={{
                      background: "linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)",
                      color: "#ffffff",
                      border: "none",
                      padding: "4px 10px",
                      fontSize: "12px",
                      fontWeight: 700,
                      borderRadius: "6px",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <HeartPulse size={14} /> AI First-Aid Companion
                  </button>
                  <Badge value={q.data.status} />
                  <a
                    href={apiUrl("/public/track/" + encodeURIComponent(code!) + "/report")}
                    className="secondary"
                    style={{
                      padding: "4px 8px",
                      fontSize: "12px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      textDecoration: "none",
                      borderRadius: "6px",
                    }}
                  >
                    <Download size={14} /> PDF
                  </a>
                </div>
              }
            >
              {companionOpen && (
                <div
                  style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: "rgba(0, 0, 0, 0.85)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 2000,
                    padding: "1rem",
                  }}
                >
                  <div style={{ maxWidth: "900px", width: "100%" }}>
                    <EmergencyCompanion
                      trackingCode={code}
                      initialCategory={q.data?.category || "medical"}
                      onClose={() => setCompanionOpen(false)}
                    />
                  </div>
                </div>
              )}
              <ol className="timeline">
                {q.data.timeline.map((e: any, i: number) => (
                  <li key={i}>
                    <span className="timeline-dot">
                      <CheckCircle2 size={15} />
                    </span>
                    <div>
                      <strong>{label(e.kind)}</strong>
                      <small>{date(e.at)}</small>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>

            {!["closed", "duplicate", "rejected"].includes(q.data.status) && (
              <>
                <Panel title="Add Information or Updates">
                  <DataForm
                    path={"/public/track/" + code + "/notes"}
                    fields={[
                      {
                        name: "text",
                        label: "Additional details from caller",
                        type: "textarea",
                      },
                    ]}
                    submit="Send update"
                  />
                </Panel>
                <Panel title="Attach Photo or Audio Evidence">
                  <p className="muted">
                    JPEG, PNG, WebP, WAV or WebM (Maximum 10 MB). Evidence is securely stored and accessible to dispatch operators.
                  </p>
                  <label className="upload">
                    {uploading ? "Uploading…" : "Choose evidence file"}
                    <input
                      disabled={uploading}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,audio/wav,audio/webm"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        setUploadError(null);
                        setUploaded(false);
                        setUploading(true);
                        const data = new FormData();
                        data.append("file", file);
                        try {
                          await api(
                            "/public/track/" + code + "/evidence",
                            "POST",
                            data,
                          );
                          setUploaded(true);
                        } catch (error) {
                          setUploadError(error);
                        } finally {
                          setUploading(false);
                        }
                      }}
                    />
                  </label>
                  <ErrorBox error={uploadError} />
                  {uploaded && (
                    <p role="status" className="success" style={{ color: "#10b981", marginTop: "0.5rem" }}>
                      ✓ Evidence uploaded and attached to case.
                    </p>
                  )}
                </Panel>
              </>
            )}
          </>
        )}
      </main>
    </>
  );
}
