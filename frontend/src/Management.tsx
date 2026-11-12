import { RoleRequestReview } from "./Auth";
import { apiList, apiCollection } from "./api";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, User, label, date } from "./api";
import {
  PageHead,
  Panel,
  Empty,
  Loading,
  ErrorBox,
  DataForm,
  Action,
  Badge,
} from "./components";
import { Map } from "./Map";
export function Analytics() {
  const q = useQuery({
    queryKey: ["analytics"],
    queryFn: () => api("/analytics"),
  });
  const d = q.data;
  return (
    <>
      <PageHead eyebrow="TERA Insights" title="Understand the response.">
        Analysis from recorded incidents, missions and capacity.
      </PageHead>
      <ErrorBox error={q.error} />
      {q.isLoading ? (
        <Loading />
      ) : (
        d && (
          <>
            <div className="metrics four">
              <div>
                <span>Recorded incidents</span>
                <strong>{d.total_incidents}</strong>
                <small>All available history</small>
              </div>
              <div>
                <span>Mean acknowledgement</span>
                <strong>
                  {d.mean_acknowledgement_seconds === null
                    ? "—"
                    : (d.mean_acknowledgement_seconds / 60).toFixed(1)}
                  <small> min</small>
                </strong>
                <small>
                  {d.mean_acknowledgement_seconds === null
                    ? "No acknowledged missions"
                    : "Report → responder acknowledgement"}
                </small>
              </div>
              <div>
                <span>Occupied capacity</span>
                <strong>
                  {d.capacity.total
                    ? Math.round(
                        (d.capacity.occupied / d.capacity.total) * 100,
                      ) + "%"
                    : "—"}
                </strong>
                <small>
                  {d.capacity.occupied} of {d.capacity.total} registered beds
                </small>
              </div>
              <div>
                <span>Assigned ambulances</span>
                <strong>
                  {d.fleet.assigned}
                  <small> / {d.fleet.total}</small>
                </strong>
                <small>Currently active missions</small>
              </div>
            </div>
            <div className="two-col">
              <Panel title="Incident categories">
                <Bars data={d.by_category} />
              </Panel>
              <Panel title="Lifecycle distribution">
                <Bars data={d.by_status} />
              </Panel>
              <Panel title="Referral outcomes">
                <Bars data={d.referrals} />
              </Panel>
              <Panel title="Capacity utilization">
                <Bars
                  data={{
                    occupied: d.capacity.occupied,
                    reserved: d.capacity.reserved,
                    available:
                      d.capacity.total -
                      d.capacity.occupied -
                      d.capacity.reserved,
                  }}
                />
              </Panel>
            </div>
            <Panel title="Geographic trends">
              <Map
                points={d.geography.map((p: any) => ({
                  ...p,
                  name: label(p.category),
                  detail:
                    p.count +
                    " recorded incidents; coordinates grouped to 0.01°",
                }))}
              />
            </Panel>
            <p className="muted">
              Generated {date(d.generated_at)}.{" "}
              <Link to="/app">
                Open the incident archive to reconstruct individual histories.
              </Link>
            </p>
          </>
        )
      )}
    </>
  );
}
function Bars({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (!total)
    return (
      <Empty title="No measurements yet">
        This chart will appear when relevant records exist.
      </Empty>
    );
  return (
    <div className="bars">
      {Object.entries(data).map(([k, v]) => (
        <div key={k}>
          <div className="row-between">
            <span>{label(k)}</span>
            <strong>{v}</strong>
          </div>
          <div className="bar-track">
            <div style={{ width: (v / total) * 100 + "%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}
export function Resources() {
  const org = useQuery({
    queryKey: ["organizations"],
    queryFn: () => apiList<any>("/organizations"),
  });
  const fleet = useQuery({
    queryKey: ["ambulances"],
    queryFn: () => apiList<any>("/ambulances"),
  });
  const opts = (org.data || []).map((o) => ({ value: o.id, label: o.name }));
  return (
    <>
      <PageHead
        eyebrow="TERA Admin / Resource registry"
        title="Build your response network."
      >
        Register real organizations, hospitals and ambulances before dispatch.
      </PageHead>
      <ErrorBox error={org.error || fleet.error} />
      <div className="two-col">
        <Panel title="Organizations">
          <DataForm
            path="/organizations"
            submit="Create organization"
            fields={[{ name: "name", label: "Organization name" }]}
          />
          {org.data?.map((o) => (
            <div className="record" key={o.id}>
              {o.name}
              <small>{o.id}</small>
            </div>
          ))}
        </Panel>
        <Panel title="Register a hospital">
          <DataForm
            path="/hospitals"
            submit="Register hospital"
            fields={[
              { name: "organization_id", label: "Organization", options: opts },
              { name: "name", label: "Hospital name" },
              {
                name: "latitude",
                label: "Latitude (optional)",
                type: "number",
                required: false,
              },
              {
                name: "longitude",
                label: "Longitude (optional)",
                type: "number",
                required: false,
              },
            ]}
          />
        </Panel>
      </div>
      <Panel title="Ambulance registry">
        <DataForm
          path="/ambulances"
          submit="Register ambulance"
          fields={[
            { name: "organization_id", label: "Organization", options: opts },
            { name: "registration", label: "Registration number" },
          ]}
        />
        {fleet.data?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Registration</th>
                  <th>Availability</th>
                  <th>Service</th>
                </tr>
              </thead>
              <tbody>
                {fleet.data.map((a) => (
                  <tr key={a.id}>
                    <td>{a.registration}</td>
                    <td>
                      <Badge
                        value={a.available ? "available" : "unavailable"}
                      />
                    </td>
                    <td>
                      <Action
                        secondary
                        method="PATCH"
                        path={"/ambulances/" + a.id}
                        body={{ active: !a.active }}
                      >
                        {a.active ? "Remove from service" : "Return to service"}
                      </Action>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No ambulances registered" />
        )}
      </Panel>
    </>
  );
}
export function Users() {
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ["users", offset],
    queryFn: () => api("/users?limit=20&offset=" + offset),
  });
  const org = useQuery({
    queryKey: ["organizations"],
    queryFn: () => apiList<any>("/organizations"),
  });
  return (
    <>
      <PageHead
        eyebrow="TERA Admin / People"
        title="The team behind the response."
      >
        Invite operational accounts and manage access.
      </PageHead>
      <Panel title="Invite a team member">
        <DataForm
          path="/invitations"
          submit="Email invitation"
          fields={[
            { name: "email", label: "Email address", type: "email" },
            {
              name: "role",
              label: "Approved role",
              options: [
                "operator",
                "hospital",
                "responder",
                "analyst",
                "admin",
              ].map((value) => ({ value, label: label(value) })),
            },
            {
              name: "organization_id",
              label: "Organization",
              options: (org.data || []).map((o) => ({
                value: o.id,
                label: o.name,
              })),
            },
          ]}
        />
      </Panel>
      <Panel title="User accounts">
        <ErrorBox error={q.error || org.error} />
        {q.isLoading ? (
          <Loading />
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Name / email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Access</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data?.items.map((u: any) => (
                    <tr key={u.id}>
                      <td>
                        {u.name}
                        <small>{u.email}</small>
                      </td>
                      <td>
                        <Badge value={u.role} />
                      </td>
                      <td>
                        {u.suspended
                          ? "Suspended"
                          : u.verified
                            ? "Verified"
                            : "Awaiting verification"}
                      </td>
                      <td>
                        <Action
                          path={"/users/" + u.id}
                          method="PATCH"
                          secondary
                          body={{ suspended: !u.suspended }}
                        >
                          {u.suspended ? "Recover account" : "Suspend account"}
                        </Action>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <button
                className="secondary"
                disabled={!offset}
                onClick={() => setOffset(offset - 20)}
              >
                Previous
              </button>
              <span>{q.data?.total || 0} users</span>
              <button
                className="secondary"
                disabled={offset + 20 >= (q.data?.total || 0)}
                onClick={() => setOffset(offset + 20)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </Panel>
      <RoleRequestReview />
      <AccessControls />
    </>
  );
}
export function Audit() {
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ["audit", offset],
    queryFn: () => api("/audit?limit=30&offset=" + offset),
  });
  return (
    <>
      <PageHead
        eyebrow="TERA Admin / Audit trail"
        title="An accountable record."
      >
        Append-only activity history, enforced in PostgreSQL.
      </PageHead>
      <Panel title="Recorded activity">
        <ErrorBox error={q.error} />
        {q.isLoading ? (
          <Loading />
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>Target</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data?.items.map((a: any) => (
                    <tr key={a.id}>
                      <td>{label(a.action)}</td>
                      <td className="mono">{a.target}</td>
                      <td>{date(a.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <button
                className="secondary"
                disabled={!offset}
                onClick={() => setOffset(offset - 30)}
              >
                Previous
              </button>
              <span>{q.data?.total || 0} records</span>
              <button
                className="secondary"
                disabled={offset + 30 >= (q.data?.total || 0)}
                onClick={() => setOffset(offset + 30)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </Panel>
    </>
  );
}
export function Account({ user }: { user: User }) {
  const history = useQuery({
    queryKey: ["account-history"],
    queryFn: () => apiList<any>("/auth/history"),
  });
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => apiList<any>("/auth/sessions"),
  });
  const setup = useMutation({
    mutationFn: () => api("/auth/mfa/setup", "POST"),
  });
  return (
    <>
      <PageHead eyebrow="Account / Security" title="Your account, protected.">
        {user.name} · {user.email}
      </PageHead>
      <p><a href="/onboarding">Confirm profile or request a staff role</a></p>
      <Panel title="Authenticator verification">
        {user.mfa_enabled ? (
          <p className="notice success">
            An authenticator is enabled for this account.
          </p>
        ) : (
          <>
            <p>Use an authenticator app to add a second verification step.</p>
            <button
              className="primary"
              onClick={() => setup.mutate()}
              disabled={setup.isPending}
            >
              Set up authenticator
            </button>
            <ErrorBox error={setup.error} />
            {setup.data && (
              <>
                <p>Add this secret to your authenticator. Keep it private.</p>
                <code className="secret">{setup.data.secret}</code>
                <DataForm
                  path="/auth/mfa/confirm"
                  submit="Confirm authenticator"
                  fields={[{ name: "code", label: "Current six-digit code" }]}
                />
              </>
            )}
          </>
        )}
      </Panel>
      <Panel title="Active sessions">
        <ErrorBox error={sessions.error} />
        {sessions.data?.map((s) => (
          <div className="record row-between" key={s.id}>
            <div>
              <strong>{s.user_agent || "Unknown browser"}</strong>
              <small>
                Created {date(s.created_at)} · Expires {date(s.expires_at)}
              </small>
            </div>
            <Action path={"/auth/sessions/" + s.id} method="DELETE" secondary>
              Revoke
            </Action>
          </div>
        ))}
      </Panel>
      <Panel title="Account activity">
        <ErrorBox error={history.error} />
        {history.data?.map((a) => (
          <div className="record" key={a.id}>
            {label(a.action)}
            <small>{date(a.created_at)}</small>
          </div>
        ))}
      </Panel>
    </>
  );
}
export function System() {
  const q = useQuery({ queryKey: ["system"], queryFn: () => api("/system") });
  return (
    <>
      <PageHead eyebrow="TERA Admin / System" title="Deployment health.">
        Live connectivity checks and configured authentication providers.
      </PageHead>
      <ErrorBox error={q.error} />
      {q.isLoading ? (
        <Loading />
      ) : (
        q.data && (
          <Panel title="Service configuration">
            <dl className="system-grid">
              {Object.entries({
                Environment: q.data.environment,
                Database: q.data.health.database || q.data.health.status,
                Redis: q.data.health.rate_limiter || "unavailable",
                "Email configured": q.data.email_host_configured ? "Yes" : "No",
                "Google configured": q.data.google_configured ? "Yes" : "No",
                "MFA required for staff": q.data.mfa_required_privileged
                  ? "Yes"
                  : "No",
              }).map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
            </dl>
            <p className="muted">
              Deployment configuration is managed through environment variables.
              Email configuration does not confirm successful message delivery.
            </p>
          </Panel>
        )
      )}
    </>
  );
}

function AccessControls() {
  const [selected, setSelected] = useState("");
  const users = useQuery({
    queryKey: ["users", "access"],
    queryFn: () => apiCollection<any>("/users"),
  });
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => apiList<any>("/organizations"),
  });
  const permissions = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api("/permissions"),
  });
  return (
    <>
      <Panel title="Approved account access">
        <label>
          Account to manage
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Select an account…</option>
            {users.isLoading && <option disabled>Loading accounts…</option>}
            {users.data?.items.map((u: any) => (
              <option value={u.id} key={u.id}>
                {u.name} · {u.email}
              </option>
            ))}
          </select>
        </label>
        {selected && (
          <div className="spaced">
            <DataForm
              key={selected}
              path={"/users/" + selected + "/access"}
              method="PATCH"
              submit="Approve access change"
              fields={[
                {
                  name: "role",
                  label: "Role",
                  options: [
                    "citizen",
                    "operator",
                    "hospital",
                    "responder",
                    "analyst",
                    "admin",
                  ].map((value) => ({ value, label: value })),
                },
                {
                  name: "organization_id",
                  label: "Organization (required for operational roles)",
                  required: false,
                  options: (orgs.data || []).map((o) => ({
                    value: o.id,
                    label: o.name,
                  })),
                },
              ]}
              transform={(d) => ({
                ...d,
                organization_id: d.organization_id || null,
              })}
            />
          </div>
        )}
        <p className="fine-print">
          Access changes revoke existing sessions. Active responder missions
          must be completed first.
        </p>
      </Panel>
      <Panel title="Permission restrictions">
        <p className="muted">
          Restrict individual API actions within a user's role. Removing a
          restriction never grants access beyond their role or organization.
        </p>
        <ErrorBox error={users.error || orgs.error || permissions.error} />
        {users.isLoading || permissions.isLoading ? (
          <Loading />
        ) : (
          <>
            <DataForm
              path="/permissions"
              method="PUT"
              submit="Update restriction"
              fields={[
                {
                  name: "user_id",
                  label: "User",
                  options: (users.data?.items || []).map((u: any) => ({
                    value: u.id,
                    label: u.name + " · " + u.email,
                  })),
                },
                {
                  name: "action",
                  label: "Action",
                  options: (permissions.data?.actions || []).map(
                    (value: string) => ({ value, label: value }),
                  ),
                },
                {
                  name: "denied",
                  label: "Restriction",
                  options: [
                    { value: "true", label: "Restrict action" },
                    { value: "false", label: "Restore role permission" },
                  ],
                },
              ]}
              transform={(d) => ({ ...d, denied: d.denied === "true" })}
            />
            {permissions.data?.restrictions
              .filter((r: any) => r.denied)
              .map((r: any) => (
                <div className="record" key={r.id}>
                  <strong>
                    {users.data?.items.find((u: any) => u.id === r.user_id)?.name ||
                      r.user_id}
                  </strong>
                  <small>{r.action}</small>
                </div>
              ))}
          </>
        )}
      </Panel>

      <Panel
        title="Medically Approved First-Aid Protocols"
        aside={
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#10b981",
              background: "rgba(16, 185, 129, 0.1)",
              padding: "2px 8px",
              borderRadius: "4px",
            }}
          >
            13 APPROVED · 6 LANGUAGES
          </span>
        }
      >
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          These protocols are strictly verified and enforced for the TERA AI Emergency Companion. Autonomous AI guidance only serves versions that hold verified medical approval.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "0.75rem" }}>
          {[
            { id: "PROT-BLEEDING-DIRECT", category: "Severe Bleeding", title: "Direct Pressure & Elevation" },
            { id: "PROT-CARDIAC-CPR", category: "Cardiac Arrest", title: "Hands-Only Chest Compressions" },
            { id: "PROT-UNCONSCIOUS-AIRWAY", category: "Unconsciousness", title: "Airway Assessment & Recovery" },
            { id: "PROT-CHOKING-ADULT", category: "Choking", title: "Abdominal Thrusts & Back Blows" },
            { id: "PROT-BURNS-THERMAL", category: "Thermal Burns", title: "Cool Water Lavage & Protection" },
            { id: "PROT-SEIZURES-ACTIVE", category: "Seizures", title: "Cushioning & Airway Protection" },
            { id: "PROT-POISONING-INGESTION", category: "Poisoning", title: "Packaging Identification & Poison Control" },
            { id: "PROT-ROAD-COLLISION", category: "Road Accidents", title: "Scene Safety & Spinal Motion Restriction" },
            { id: "PROT-DROWNING-SUBMERSION", category: "Drowning", title: "Water Extraction & Rescue Breaths" },
            { id: "PROT-FRACTURES-IMMOBILIZATION", category: "Fractures", title: "Splinting & Pulse Checks" },
            { id: "PROT-FIRE-SMOKE", category: "Fire & Smoke", title: "Low Crawl & Smoke Evacuation" },
            { id: "PROT-ELECTRICAL-SHOCK", category: "Electrical Shock", title: "Power Disconnect & Non-Conductive Push" },
            { id: "PROT-ENVIRONMENTAL-HEAT", category: "Heat Stroke", title: "Rapid Active Cooling & Shade" },
          ].map((p) => (
            <div
              key={p.id}
              style={{
                background: "rgba(15, 23, 42, 0.03)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                padding: "0.75rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--primary)" }}>{p.category}</span>
                <span style={{ fontSize: "10px", color: "#10b981", fontWeight: 700 }}>✓ APPROVED</span>
              </div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{p.title}</div>
              <small style={{ color: "var(--muted)", fontSize: "11px" }}>{p.id}</small>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
