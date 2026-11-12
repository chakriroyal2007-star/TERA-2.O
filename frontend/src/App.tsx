import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Radio,
  HeartPulse,
  Truck,
  ChartNoAxesCombined,
  Users as UsersIcon,
  Settings,
  ShieldCheck,
  ClipboardList,
  LogOut,
  Menu,
  Bell,
  ArrowUpRight,
  Database,
} from "lucide-react";
import { api, ApiError, User, queryClient, label } from "./api";
import { Landing, ReportPage, TrackPage, Brand, PublicNav } from "./Public";
import { Login, GoogleOnboarding } from "./Auth";
import { DbmsStudio } from "./dbms/DbmsStudio";
import {
  IncidentList,
  IncidentDetail,
  Missions,
  Hospitals,
} from "./Operations";
import {
  Analytics,
  Resources,
  Users,
  Audit,
  Account,
  System,
} from "./Management";
import { Empty, ErrorBox, Loading } from "./components";
function Shell() {
  const q = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
  });
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [connection, setConnection] = useState("Connecting");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!q.data || q.data.role === "citizen") return;
    let socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout>,
      stopped = false,
      cursor = 0,
      delay = 1000,
      consecutiveErrors = 0;
    const connect = () => {
      const defaultWsHost = location.host;
      const defaultWsProto = location.protocol === "https:" ? "wss:" : "ws:";
      const wsBase =
        import.meta.env.VITE_WS_URL ||
        `${defaultWsProto}//${defaultWsHost}/api/v1/ws`;
      socket = new WebSocket(
        `${wsBase}${wsBase.includes("?") ? "&" : "?"}after=${cursor}`,
      );
      socket.onopen = () => {
        delay = 1000;
        consecutiveErrors = 0;
        setConnection("Updates connected");
      };
      socket.onmessage = (e) => {
        const event = JSON.parse(e.data);
        if (event.id) {
          cursor = event.id;
          queryClient.invalidateQueries({
            predicate: (q) => q.queryKey[0] !== "me",
          });
        }
      };
      socket.onclose = async (e) => {
        if (stopped) return;
        consecutiveErrors++;
        if (consecutiveErrors > 5) {
          setConnection("Connected");
          return;
        }
        setConnection("Reconnecting");
        if (e.code === 4401) {
          try {
            await api("/auth/refresh", "POST");
          } catch {
            queryClient.invalidateQueries({ queryKey: ["me"] });
            return;
          }
        }
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [q.data?.id]);
  if (q.isLoading || (q.isFetching && !q.data)) return <Loading />;
  if (q.error instanceof ApiError && q.error.status === 401)
    return <Navigate to="/login" replace />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const user = q.data;
  const links = [
    {
      to: "/app",
      name: "Incident desk",
      icon: LayoutDashboard,
      roles: ["operator", "admin", "analyst", "hospital", "responder"],
    },
    {
      to: "/app/dbms",
      name: "DBMS Studio",
      icon: Database,
      roles: ["operator", "admin", "analyst"],
    },
    {
      to: "/app/missions",
      name: "Field missions",
      icon: Truck,
      roles: ["operator", "admin", "analyst", "responder"],
    },
    {
      to: "/app/hospitals",
      name: "Hospital network",
      icon: HeartPulse,
      roles: ["operator", "admin", "analyst", "hospital"],
    },
    {
      to: "/app/analytics",
      name: "Insights",
      icon: ChartNoAxesCombined,
      roles: ["operator", "admin", "analyst"],
    },
    { to: "/app/resources", name: "Resources", icon: Radio, roles: ["admin"] },
    {
      to: "/app/users",
      name: "People & access",
      icon: UsersIcon,
      roles: ["admin"],
    },
    {
      to: "/app/audit",
      name: "Audit trail",
      icon: ClipboardList,
      roles: ["admin"],
    },
    {
      to: "/app/system",
      name: "System health",
      icon: Settings,
      roles: ["admin"],
    },
    {
      to: "/app/account",
      name: "Account security",
      icon: ShieldCheck,
      roles: [
        "citizen",
        "operator",
        "admin",
        "analyst",
        "hospital",
        "responder",
      ],
    },
  ].filter((l) => l.roles.includes(user.role));
  const authorized = (roles: string[], element: React.ReactNode) =>
    roles.includes(user.role) ? (
      element
    ) : (
      <Empty title="This area is not available to your role" />
    );
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (open ? "open" : "")}>
        <Brand />
        <div className="workspace-tag">
          <span className="status-dot" />
          <div>
            Coordination workspace<small>{label(user.role)} portal</small>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Workspace navigation">
          {links.map((l) => (
            <NavLink
              end={l.to === "/app"}
              to={l.to}
              onClick={() => setOpen(false)}
              key={l.to}
            >
              <l.icon size={18} />
              {l.name}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Link to="/report">
            Public report form <ArrowUpRight size={15} />
          </Link>
          <div className="user-card">
            <span className="avatar">
              {user.name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.name}</strong>
              <small>{label(user.role)}</small>
            </div>
            <button
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST");
                  queryClient.clear();
                  nav("/login");
                } catch (e) {
                  setError(e);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Toggle navigation"
            onClick={() => setOpen(!open)}
          >
            <Menu />
          </button>
          <span>
            TERA <span className="slash">/</span> Coordination platform
          </span>
          <div>
            <span
              className={
                "connection " +
                (connection === "Updates connected" ? "connected" : "")
              }
            >
              {user.role === "citizen" ? "Citizen account" : connection}
            </span>
            <Link aria-label="Account security" to="/app/account">
              <ShieldCheck size={18} />
            </Link>
          </div>
        </header>
        <main className="workspace-content">
          <ErrorBox error={error} />
          <Routes>
            <Route
              index
              element={
                user.role === "citizen" ? (
                  <Empty title="Ready when you need to report">
                    <Link to="/report">Report an emergency</Link> or{" "}
                    <Link to="/track">track an existing report</Link>.
                  </Empty>
                ) : (
                  <IncidentList user={user} />
                )
              }
            />
            <Route
              path="incidents/:id"
              element={authorized(
                ["operator", "admin", "analyst", "responder", "hospital"],
                <IncidentDetail user={user} />,
              )}
            />
            <Route
              path="missions"
              element={authorized(
                ["operator", "admin", "analyst", "responder"],
                <Missions user={user} />,
              )}
            />
            <Route
              path="hospitals"
              element={authorized(
                ["operator", "admin", "analyst", "hospital"],
                <Hospitals user={user} />,
              )}
            />
            <Route
              path="analytics"
              element={authorized(
                ["operator", "admin", "analyst"],
                <Analytics />,
              )}
            />
            <Route
              path="dbms/*"
              element={authorized(
                ["operator", "admin", "analyst"],
                <DbmsStudio user={user} />,
              )}
            />
            <Route
              path="resources"
              element={authorized(["admin"], <Resources />)}
            />
            <Route path="users" element={authorized(["admin"], <Users />)} />
            <Route path="audit" element={authorized(["admin"], <Audit />)} />
            <Route path="system" element={authorized(["admin"], <System />)} />
            <Route path="account" element={<Account user={user} />} />
            <Route
              path="*"
              element={
                <Empty title="Page not found">
                  <Link to="/app">Return to your workspace</Link>
                </Empty>
              }
            />
          </Routes>
        </main>
        <div className="workspace-footer">
          TERA 2.0 <span>One network. A coordinated response.</span>
        </div>
      </div>
    </div>
  );
}
export function PublicDbmsPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#0b1916" }}>
      <PublicNav />
      <div style={{ flex: 1, padding: "1.25rem", maxWidth: "1600px", width: "100%", margin: "0 auto" }}>
        <DbmsStudio />
      </div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/report" element={<ReportPage />} />
      <Route path="/track" element={<TrackPage />} />
      <Route path="/track/:code" element={<TrackPage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/onboarding" element={<GoogleOnboarding />} />
      <Route path="/dbms" element={<PublicDbmsPage />} />
      <Route path="/dbms/*" element={<PublicDbmsPage />} />
      <Route path="/app/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
