import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, ShieldCheck } from "lucide-react";
import { api, apiUrl, queryClient, User } from "./api";
import { Brand } from "./Public";
import { ErrorBox } from "./components";
export function Login() {
  const [params] = useSearchParams();
  const invitation = params.get("invitation") || "";
  const [mode, setMode] = useState(invitation ? "register" : "password");
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [mfa, setMfa] = useState("");
  const [message, setMessage] = useState("");
  const nav = useNavigate();
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api("/auth/providers"),
  });
  const m = useMutation({
    mutationFn: async () => {
      if (mode === "password")
        return api("/auth/login", "POST", {
          email,
          password,
          mfa_code: mfa || null,
        });
      if (mode === "register")
        return api("/auth/register", "POST", {
          email,
          password,
          name,
          invitation: invitation || null,
        });
      const purpose =
        mode === "otp" ? "login" : mode === "reset" ? "reset" : "verify";
      return sent
        ? api("/auth/otp/verify", "POST", {
            email,
            purpose,
            code,
            password: mode === "reset" ? password : null,
            mfa_code: mfa || null,
          })
        : api("/auth/otp/request", "POST", { email, purpose });
    },
    onSuccess: (data: any) => {
      if (
        mode === "password" ||
        (mode === "otp" && sent) ||
        (mode === "verify" && sent)
      ) {
        if (data && data.id && data.role) {
          queryClient.setQueryData(["me"], data);
          const r = String(data.role).toLowerCase();
          if (r === "hospital") nav("/app/hospitals");
          else if (r === "responder") nav("/app/missions");
          else if (r === "analyst") nav("/app/analytics");
          else nav("/app");
        } else {
          api<User>("/auth/me")
            .then((me) => {
              queryClient.setQueryData(["me"], me);
              const r = String(me.role).toLowerCase();
              if (r === "hospital") nav("/app/hospitals");
              else if (r === "responder") nav("/app/missions");
              else if (r === "analyst") nav("/app/analytics");
              else nav("/app");
            })
            .catch(() => {
              queryClient.invalidateQueries({ queryKey: ["me"] });
              nav("/app");
            });
        }
        return;
      }
      setMessage(data.message);
      if (mode === "register") {
        setMode("verify");
        setSent(true);
      } else if (!sent) {
        setSent(true);
      } else {
        setMode("password");
        setSent(false);
      }
    },
  });
  const title =
    mode === "register"
      ? "Join the response."
      : mode === "reset"
        ? "Recover your account."
        : mode === "verify"
          ? "Verify your email."
          : "Welcome back.";
  const [directRole, setDirectRole] = useState<string | null>(null);
  const [directError, setDirectError] = useState<unknown>(null);

  const handleDirectLogin = async (accEmail: string, roleName: string, accPassword = "Emergency@2025!") => {
    setDirectRole(roleName);
    setDirectError(null);
    setEmail(accEmail);
    setPassword(accPassword);
    try {
      const user = await api<User>("/auth/login", "POST", {
        email: accEmail,
        password: accPassword,
        mfa_code: null,
      });
      // Synchronously populate user in cache to eliminate 401 redirect race condition
      queryClient.setQueryData(["me"], user);
      
      const r = (user.role || roleName).toLowerCase();
      if (r === "hospital") {
        nav("/app/hospitals");
      } else if (r === "responder") {
        nav("/app/missions");
      } else if (r === "analyst") {
        nav("/app/analytics");
      } else {
        nav("/app");
      }
    } catch (err) {
      setDirectError(err);
      setDirectRole(null);
    }
  };

  function change(next: string) {
    setMode(next);
    setSent(false);
    setMessage("");
    m.reset();
  }

  const DEMO_ROLES = [
    { role: "Operator", email: "operator@example.com", desc: "Triage Desk", badge: "Live Queue", icon: "🛡️" },
    { role: "Admin", email: "admin@example.com", desc: "System Config", badge: "Admin", icon: "⚡" },
    { role: "Responder", email: "responder@example.com", desc: "Field Fleet", badge: "Ambulance", icon: "🚑" },
    { role: "Hospital", email: "hospital@example.com", desc: "Trauma Care", badge: "ICU / Bed", icon: "🏥" },
    { role: "Analyst", email: "analyst@example.com", desc: "Crisis Intel", badge: "Analytics", icon: "📊" },
    { role: "Citizen", email: "citizen@example.com", desc: "Reporter", badge: "Citizen", icon: "👤" },
  ];
  return (
    <main className="auth-layout">
      <aside className="auth-story">
        <Brand />
        <div>
          <div className="eyebrow light">
            A shared picture. A coordinated response.
          </div>
          <h1>
            Connected teams.
            <br />
            <em>Better prepared.</em>
          </h1>
          <p>
            One place for the people who report, coordinate, respond and care.
          </p>
          <div className="auth-line">
            <Activity size={60} />
            <span>
              Every second matters.
              <br />
              Every action is recorded.
            </span>
          </div>
        </div>
        <small>TERA · Emergency coordination platform</small>
      </aside>
      <section className="auth-main">
        <Link to="/" className="back-link">
          ← Back to TERA
        </Link>
        <div className="auth-form">
          <div
            style={{
              background: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              borderRadius: "8px",
              padding: "0.75rem 1rem",
              marginBottom: "1.25rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "0.75rem",
            }}
          >
            <div>
              <strong style={{ color: "#34d399", fontSize: "0.9rem", display: "block" }}>
                🗄️ DBMS Project Evaluation
              </strong>
              <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                Inspect live schema, Chen ER diagram & SQL Lab directly.
              </span>
            </div>
            <Link
              to="/dbms"
              style={{
                padding: "0.35rem 0.75rem",
                background: "#10b981",
                color: "#0b1916",
                borderRadius: "6px",
                fontWeight: 700,
                fontSize: "0.8rem",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              Open Studio →
            </Link>
          </div>
          <div className="eyebrow">Secure team access</div>
          <h2>{title}</h2>
          <p>Use your verified account to continue.</p>

          {/* 1-Click Quick Admin Access */}
          <div style={{
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            borderRadius: "10px",
            padding: "0.85rem",
            marginBottom: "1.25rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem"
          }}>
            <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#34d399", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              ⚡ 1-Click Administrator Sign-In
            </div>
            <button
              type="button"
              disabled={directRole === "Admin"}
              onClick={() => handleDirectLogin("beesvenkatrahul@gmail.com", "Admin", "Emergency@2025!")}
              style={{
                width: "100%",
                padding: "0.6rem 0.85rem",
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontWeight: 700,
                fontSize: "0.88rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                boxShadow: "0 2px 8px rgba(16, 185, 129, 0.25)"
              }}
            >
              <span>👤 Venkat Rahul (Admin)</span>
              <span style={{ fontSize: "0.75rem", opacity: 0.9 }}>
                {directRole === "Admin" ? "Authenticating..." : "1-Click Login →"}
              </span>
            </button>
            <button
              type="button"
              disabled={directRole === "Chakri"}
              onClick={() => handleDirectLogin("chakriroyal2007@gmail.com", "Chakri", "Emergency@2025!")}
              style={{
                width: "100%",
                padding: "0.5rem 0.85rem",
                background: "rgba(16, 185, 129, 0.15)",
                color: "#34d399",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                borderRadius: "6px",
                fontWeight: 600,
                fontSize: "0.84rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between"
              }}
            >
              <span>👤 Chakri (Admin)</span>
              <span style={{ fontSize: "0.75rem", opacity: 0.8 }}>
                {directRole === "Chakri" ? "Authenticating..." : "1-Click Login →"}
              </span>
            </button>
          </div>

          {mode === "password" && (
            <>
              {providers.data?.google && (
                <>
                  <a className="google-button" href={apiUrl("/auth/google")}>
                    <strong aria-hidden="true">G</strong> Continue with Google
                  </a>
                  <small style={{ color: "#94a3b8", fontSize: "0.78rem", display: "block", marginTop: "0.35rem", textAlign: "center" }}>
                    If Google shows "redirect_uri_mismatch", use the 1-Click Admin buttons above.
                  </small>
                  <div className="divider">or use your email</div>
                </>
              )}
              {providers.data && !providers.data.google && (
                <small className="muted">
                  Google sign-in is currently unavailable. Sign in with your email below.
                </small>
              )}
              <div className="tabs">
                <button className="active" onClick={() => change("password")}>
                  Password
                </button>
                <button onClick={() => change("otp")}>Email code</button>
              </div>
            </>
          )}
          <form
            className="data-form"
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate();
            }}
          >
            {mode === "register" && (
              <label>
                Full name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  minLength={2}
                  autoComplete="name"
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                readOnly={sent}
              />
            </label>
            {["password", "register"].includes(mode) ||
            (mode === "reset" && sent) ? (
              <label>
                {mode === "reset" ? "New password" : "Password"}
                <input
                  type="password"
                  minLength={mode === "password" ? 1 : 12}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={
                    mode === "password" ? "current-password" : "new-password"
                  }
                  required
                />
              </label>
            ) : null}
            {sent && (
              <label>
                Six-digit email code
                <input
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
              </label>
            )}
            {mode === "password" || sent ? (
              <details>
                <summary>Use an authenticator code</summary>
                <label>
                  Authenticator code
                  <input
                    inputMode="numeric"
                    maxLength={6}
                    value={mfa}
                    onChange={(e) => setMfa(e.target.value)}
                  />
                </label>
              </details>
            ) : null}
            <ErrorBox error={m.error} />
            {message && (
              <div className="notice success" role="status">
                {message}
              </div>
            )}
            <button className="primary" disabled={m.isPending}>
              {m.isPending
                ? "Please wait…"
                : mode === "password"
                  ? "Sign in"
                  : mode === "register"
                    ? "Create account"
                    : sent
                      ? "Verify code"
                      : "Send email code"}
              <ArrowUpRight size={17} />
            </button>
          </form>

          {directError ? <ErrorBox error={directError} /> : null}

          {import.meta.env.VITE_EVALUATION_LOGIN === "true" && <div
            style={{
              marginTop: "1.25rem",
              padding: "1rem",
              background: "rgba(16, 40, 36, 0.75)",
              borderRadius: "10px",
              border: "1px solid #1a3c36",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.2)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.6rem",
              }}
            >
              <span
                style={{
                  fontSize: "0.82rem",
                  color: "#34d399",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                }}
              >
                ⚡ 1-Click Instant Role Access
              </span>
              <span
                style={{
                  fontSize: "0.68rem",
                  color: "#94a3b8",
                  background: "rgba(255, 255, 255, 0.06)",
                  padding: "2px 6px",
                  borderRadius: "4px",
                }}
              >
                Direct Login
              </span>
            </div>
            <p
              style={{
                fontSize: "0.74rem",
                color: "#94a3b8",
                margin: "0 0 0.75rem 0",
                lineHeight: "1.4",
              }}
            >
              Click any role to immediately sign in and launch that authorized portal:
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "0.5rem",
              }}
            >
              {DEMO_ROLES.map((acc) => {
                const isLoggingIn = directRole === acc.role;
                return (
                  <button
                    key={acc.email}
                    type="button"
                    disabled={directRole !== null || m.isPending}
                    onClick={() => handleDirectLogin(acc.email, acc.role)}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      textAlign: "left",
                      background: isLoggingIn ? "#047857" : "#0a1f1b",
                      color: "#f8fafc",
                      border: "1px solid " + (isLoggingIn ? "#10b981" : "#1a3c36"),
                      padding: "8px 10px",
                      borderRadius: "6px",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                    title={`Click to directly sign in as ${acc.role} (${acc.email})`}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                        fontSize: "0.82rem",
                        fontWeight: 700,
                        color: isLoggingIn ? "#fff" : "#34d399",
                        width: "100%",
                      }}
                    >
                      <span>{acc.icon}</span>
                      <span>{acc.role}</span>
                    </div>
                    <small
                      style={{
                        fontSize: "0.68rem",
                        color: isLoggingIn ? "#e2e8f0" : "#94a3b8",
                        marginTop: "2px",
                      }}
                    >
                      {isLoggingIn ? "Logging in…" : acc.desc}
                    </small>
                  </button>
                );
              })}
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: "0.6rem",
                fontSize: "0.7rem",
                color: "#64748b",
              }}
            >
              <span>
                Standard password: <code>test-passphrase-123</code>
              </span>
              <span style={{ color: "#10b981" }}>✓ All 6 Roles Active</span>
            </div>
          </div>}
          <div className="auth-links">
            {mode === "password" ? (
              <>
                <button onClick={() => change("reset")}>
                  Forgot password?
                </button>
                <button onClick={() => change("verify")}>Verify email</button>
              </>
            ) : (
              <button onClick={() => change("password")}>
                Back to password sign in
              </button>
            )}
            {sent && (
              <button
                onClick={() => {
                  setSent(false);
                  setMessage(
                    "You can request a new code after the 60-second cooldown.",
                  );
                }}
              >
                Request another code
              </button>
            )}
          </div>
          <div className="auth-bottom">
            {mode === "register" ? "Already have an account?" : "New to TERA?"}{" "}
            <button
              onClick={() =>
                change(mode === "register" ? "password" : "register")
              }
            >
              {mode === "register" ? "Sign in" : "Create an account"}
            </button>
          </div>
          <div className="privacy-note">
            <ShieldCheck size={16} />
            Operational access is granted by administrator invitation.
          </div>
          <Link className="report-link" to="/report">
            Reporting an emergency? Continue without an account →
          </Link>
        </div>
      </section>
    </main>
  );
}

export function GoogleOnboarding() {
  const nav = useNavigate();
  const [name, setName] = useState<string | null>(null);
  const [role, setRole] = useState("citizen");
  const [saved, setSaved] = useState<any>(null);
  const profile = useQuery({queryKey:["onboarding"], queryFn:() => api<any>("/auth/onboarding"), retry:false});
  const save = useMutation({mutationFn:() => api<any>("/auth/onboarding", "POST", {name:name ?? profile.data?.name, intended_role:role}), onSuccess: async data => {setSaved(data); await queryClient.invalidateQueries({queryKey:["me"]});}});
  return <main className="page-shell"><section className="panel data-form" style={{maxWidth:600, margin:"3rem auto"}}>
    <h1>Confirm your profile</h1><ErrorBox error={profile.error || save.error}/>
    {profile.data && <><label>Full name<input value={name ?? profile.data.name} onChange={e=>setName(e.target.value)} maxLength={160}/></label>
    <label>Intended role<select value={role} onChange={e=>setRole(e.target.value)}>
      <option value="citizen">Citizen</option><option value="operator">Operator</option><option value="responder">Field Responder</option><option value="hospital">Hospital Coordinator</option><option value="admin">Admin</option><option value="analyst">Analyst</option>
    </select></label><p>Staff roles require administrator approval. Your current access ({profile.data.role}) stays unchanged until approval.</p>
    <button disabled={save.isPending} onClick={()=>save.mutate()}>Save profile</button></>}
    {saved && <><p role="status">{saved.request_status === "pending" ? "Role request saved for administrator review. You can continue with your current access." : "Profile saved."}</p><button onClick={()=>nav(saved.role === "hospital" ? "/app/hospitals" : saved.role === "responder" ? "/app/missions" : saved.role === "analyst" ? "/app/analytics" : "/app")}>Continue to dashboard</button></>}
    {profile.error && <Link to="/login">Sign in to continue</Link>}
  </section></main>;
}

export function RoleRequestReview() {
  const [org, setOrg] = useState("");
  const requests = useQuery({queryKey:["role-requests"], queryFn:()=>api<any[]>("/auth/role-requests")});
  const orgs = useQuery({queryKey:["role-request-organizations"], queryFn:()=>api<any[]>("/organizations")});
  const decision = useMutation({mutationFn:({id,approve}:{id:string;approve:boolean})=>api(`/auth/role-requests/${id}`,"POST",{approve,organization_id:org || null}), onSuccess:()=>queryClient.invalidateQueries({queryKey:["role-requests"]})});
  return <section className="panel"><h2>Role approval requests</h2><ErrorBox error={requests.error || decision.error}/>
    <label>Organization for approved access<select value={org} onChange={e=>setOrg(e.target.value)}><option value="">Select organization</option>{orgs.data?.map((o:any)=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
    {requests.data?.length === 0 && <p>No pending requests.</p>}
    {requests.data?.map(r=><div key={r.id}><p>{r.name} ({r.email}) requests {r.requested_role}</p><button disabled={!org || decision.isPending} onClick={()=>decision.mutate({id:r.id,approve:true})}>Approve</button> <button className="secondary" disabled={decision.isPending} onClick={()=>decision.mutate({id:r.id,approve:false})}>Reject</button></div>)}
  </section>;
}
