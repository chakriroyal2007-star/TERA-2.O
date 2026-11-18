# TERA 2.0

A new PostgreSQL-backed emergency coordination application with six role-specific portals. This repository is independent of the original `dbms_project`. It contains a working citizen → operator → responder → hospital → closure workflow, real persistence, authentication, private evidence storage integration and automated tests.

![TERA desktop interface](docs/landing-desktop.png)

## Run locally

For another laptop, follow [the second-laptop setup guide](docs/SECOND_LAPTOP_SETUP.md). It covers fresh secrets, Google callback ports, initial administrator creation and persistent data.

Prerequisites: Docker Engine/Desktop with Compose v2, Git, and available ports 8080 and 8025.

```sh
python3 infrastructure/configure_local.py
# The guide above also provides Docker-based commands if Python is not installed.
# Add provider credentials to the generated root .env locally.
docker compose up --build
```

For a disposable local evaluation, `docker compose up --build` also works without `.env` using the explicitly development-only defaults. Production mode rejects the shipped secrets.

Open:

- Application: http://localhost:8080
- API documentation: http://localhost:8080/api/docs
- Local SMTP inbox: http://localhost:8025

Create the first administrator interactively in another terminal:

```sh
docker compose exec backend python -m app.bootstrap
```

There are no default users, demo incidents or seeded operational records. Bootstrap asks for your administrator email, name, control organization and password. It refuses to run if an administrator already exists. Sign in, use **People & access** to invite staff, and use **Resources** to register actual hospitals and ambulances.

### Set up the first complete response

1. Bootstrap an administrator and a control organization.
2. In **Resources**, create a hospital organization and hospital, and register an ambulance under the control organization.
3. Invite an operator and responder into the control organization; invite a hospital coordinator into the hospital organization. Invitations arrive in Mailpit locally. Each invited user registers using the emailed link and verifies their email with a real SMTP code.
4. In **Hospital network**, create a department and its verified bed capacity.
5. Submit an emergency through the public report form and save its tracking code.
6. The operator verifies, assigns the available ambulance/responder, and requests a hospital referral.
7. The responder acknowledges and progresses through en route and on scene. The hospital accepts the referral, reserving a bed.
8. The responder records transport and handover. The hospital confirms receipt; the responder completes the mission; the operator closes the incident.
9. Refresh the portals or restart the backend: the records remain in PostgreSQL.

The platform requires a configured, staffed response organization. Starting the software does not connect reports to a public emergency service.

## Implemented functionality

- Citizen reporting without registration; actual GPS or manual coordinates; private tracking codes; status history, additional reports and image/audio uploads.
- Operator intake, organization claiming, verification, priority reassessment, duplicate review, resource dispatch, hospital referrals and closure.
- Hospital/department registration, ICU/emergency/general capacity, reservations, referral decisions, handover confirmation and capacity history.
- Responder assignment acknowledgement and validated mission transitions, with explicit one-time GPS sharing and update timestamps.
- Analyst statistics, response acknowledgement times, capacity/fleet utilization, category/geographic trends and incident history.
- Administrator invitations, organizations, resources, account approval/access changes, suspension/recovery, permission restrictions, immutable audit history and health/configuration views.
- Password and email-code sign-in, verified registration, password reset, genuine Google OIDC integration, optional TOTP, session management and rotating/revocable refresh credentials.
- Authenticated WebSocket event replay with reconnection, backed by persisted events and scoped to the user.

The exact boundaries and deliberate simplifications are in [architecture.md](docs/architecture.md) and the [verification report](docs/verification.md). This is not a claim of certification or readiness for unsupervised emergency-service deployment.

## TERA DBMS Studio (Academic Mini-Project Evaluation)

TERA includes a dedicated **DBMS Studio** (`/app/dbms`) for academic database evaluation and live technical viva:

The evaluation environment uses the guarded `tests/seed_e2e.py` fixture described below. It creates real PostgreSQL records for six `ROLE@example.com` accounts with the test-only password `test-passphrase-123`. Login never provisions accounts. Optional role shortcut buttons require `VITE_EVALUATION_LOGIN=true`; keep this disabled outside the isolated evaluation environment.

### Academic Documentation & Assessment Deliverables

- [Complete DBMS Project Report (33 Sections)](docs/DBMS_PROJECT_REPORT.md)
- [Master DBMS Viva Preparation Guide (40 Q&As)](docs/DBMS_VIVA_PREPARATION_40_QA.md)
- [Live Demonstration Plan & Script (10 Minutes)](docs/LIVE_DEMONSTRATION_PLAN.md)
- [SQL Queries Used in TERA Reference Catalog](docs/SQL_QUERIES_USED_IN_TERA.md)

### 20-Mark Assessment Rubric Summary

| Assessment Category | Marks | Implementation & Verification |
|---|:---:|---|
| **1. Database Design** | 3 | 41 normalized tables in 3NF; PKs/FKs on all tables; Peter Chen ER Model. |
| **2. Access & Roles** | 2 | RBAC matrix covering 6 roles with backend API enforcement. |
| **3. Core Workflows** | 4 | 5 complete end-to-end workflows (Reporting, Dispatch, Lifecycle, Referral, Search). |
| **4. Technical Validation** | 3 | Nontrivial business rule preventing double ambulance assignment via partial index & row locks. |
| **5. Connectivity & Integrity** | 2 | Real PostgreSQL persistence; ACID rollback verification. |
| **6. Query Complexity & Reports** | 2 | SQL JOIN and aggregate GROUP BY reports; arbitrary SQL Lab access is administrator-only. |
| **7. Usability & CRUD** | 2 | Responsive UI with 1-click test logins, real-time error feedback, and data dictionary export. |
| **8. Documentation & Viva** | 2 | Comprehensive project report, 40-question viva guide, and reproducible test suite. |
| **Total available** | **20** | Assessed by the evaluator using the live demonstration and recorded test evidence. |

---

## External providers

### Email

The default SMTP service is Mailpit: messages are actually sent and captured locally at port 8025. They do not arrive in external inboxes. Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS` and a verified `MAIL_FROM` for external delivery. There is no code-printing or fake verification path in the application.

### Google Sign-In

Create a Google OAuth web client and set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Register this exact redirect URI for local Compose:

```text
http://localhost:8080/api/v1/auth/google/callback
```

For the audited local app on port 5173, set `PUBLIC_URL=http://localhost:5173` and register `http://localhost:5173/api/v1/auth/google/callback` instead. Both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` must be nonblank in the **backend process environment**. Keep the secret out of frontend `VITE_*` variables. Restart the backend after configuring it; Compose environment changes require recreating the backend container. Confirm `/api/v1/auth/providers` returns `"google": true` before testing consent.

For production, use `${PUBLIC_URL}/api/v1/auth/google/callback` with HTTPS. Until both credentials are present, the login page offers email sign-in and explains that Google is unavailable. Public Google sign-in creates citizen accounts; it cannot choose a privileged role. Live Google authorization requires your external client configuration and was not performed during local verification. See [the Google sign-in follow-up and consolidated testing record](docs/GOOGLE_SIGN_IN_FOLLOWUP.md).

### Object storage and maps

Compose stores files in a persistent local volume by default. MinIO is an optional `object-storage` profile. For an existing S3-compatible service, set `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` and `S3_BUCKET`; the deployment operator must create the private bucket and least-privilege credentials. Evidence downloads go through the authorized API rather than public URLs.

Leaflet uses OpenStreetMap tiles with attribution. Map pins use recorded coordinates only. Select an appropriate tile provider and comply with its usage policy for production traffic. Maps are not a route-time or medical suitability service.

## Development and tests

Backend: Python 3.12+, PostgreSQL 16+, Redis. Frontend: Node 22.14+ (the verified runtime was Node 22.23.2).

Start isolated test services:

```sh
docker compose -f infrastructure/docker-compose.test.yml up -d --wait
cd backend
uv sync --frozen --extra test
uv run pytest -q
```

The backend suite refuses to clean any database whose name does not end in `_test`. It truncates the isolated test tables between tests. Never point its environment at an operational database. PostgreSQL/Redis defaults for tests are localhost ports 55432 and 56379 respectively.

Frontend:

```sh
cd frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run e2e
```

The standalone browser run executes the public UI check and explicitly skips backend-dependent tests. To run the full browser lifecycle, create a separate PostgreSQL database named `tera_e2e_test`, set the backend environment as shown below, migrate and load the guarded test fixture:

```sh
cd backend
export DATABASE_URL=postgresql+psycopg://postgres:tera-test@127.0.0.1:55432/tera_e2e_test
export REDIS_URL=redis://127.0.0.1:56379/14
export SECRET_KEY=isolated-test-secret-minimum-32-characters
export PUBLIC_URL=http://localhost:5173
export TESTING=true
uv run alembic upgrade head
PYTHONPATH=. uv run python tests/seed_e2e.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In separate terminals:

```sh
cd frontend
npm run dev -- --port 5173
# Then, from another terminal in frontend/:
TERA_E2E_URL=http://localhost:5173 npm run e2e
```

Use a fresh E2E database when repeating the complete acceptance run; the fixture intentionally does not erase historical records. The E2E staff credentials appear only in guarded test code. `PLAYWRIGHT_CHANNEL=chrome` can use an installed Chrome browser instead of Playwright Chromium.

The public `/dbms` link redirects to the authenticated Studio. Operators and analysts can inspect schema metadata; only administrators can query raw tables or view database-wide activity.

Backend changes can be served with `uv run uvicorn app.main:app --reload`; set `PUBLIC_URL` to match the browser origin. Production Compose uses Nginx to proxy both REST and WebSockets. Vercel static hosting alone does not provide this backend, PostgreSQL, Redis or persistent file storage.

## TERA 2.0 Research Optimization Engine & Interactive Map

TERA 2.0 integrates mathematical optimization algorithms, capacity-constrained multi-patient ambulance allocation, Dijkstra shortest path routing on weighted road networks, multi-factor hospital cost ranking, and Swiggy-like live ambulance movement tracking.

### 1. Dynamic Emergency Priority Scoring (Weighted 4-Factor Model)

All simultaneous incidents are prioritized using a dynamic multi-factor model:

$$\text{Priority Score} = 0.40 \times \text{Severity} + 0.25 \times \text{WaitingTime} + 0.20 \times \text{PatientCount} + 0.15 \times \text{ResourceUrgency}$$

- **Severity Score (0–100)**: Critical ($100$), High ($75$), Medium ($50$), Low ($25$).
- **Waiting Time Score (0–100)**: $+5.0$ points per elapsed minute from report time (max 100).
- **Patient Count Score (0–100)**: $+25.0$ points per casualty ($1\text{p}=25$, $2\text{p}=50$, $3\text{p}=75$, $\ge 4\text{p}=100$).
- **Resource Urgency Score (0–100)**: Cardiac, Stroke, Burns, Trauma ($100$), Accidents ($85$), Medical ($60$).
- **Configurable Weights**: Administrators can adjust weights dynamically via `PATCH /api/v1/optimization/weights`.

### 2. Dijkstra's Shortest Path Road Network Algorithm

- Implemented via a binary min-heap (`heapq`) in `app.optimization.dijkstra`.
- Real road network nodes (intersections) and weighted edges (road distance in meters and travel time in seconds).
- Hybrid architecture: Uses OSRM road directions when reachable; executes Dijkstra shortest path on local road graph as validated fallback. Never fabricates straight-line paths as road geometry.

### 3. Capacity-Constrained Multi-Patient Ambulance Allocation

$$\min Z = \sum_{i} \sum_{j} C_{ij} X_{ij}$$

Subject to:
- $\sum_{i} X_{ij} \le 1$ (no double assignment: each ambulance assigned to at most one incident).
- $\sum_{j} (\text{Capacity}_j \cdot X_{ij}) \ge \text{Patients}_i$ (satisfies multi-patient casualty counts).
- Medical suitability: ALS/ICU vehicles dispatched to critical incidents; BLS for minor injuries.

### 4. Multi-Factor Hospital Selection Optimization

$$\text{Hospital Cost} = 0.35 \times \text{TravelTime} + 0.30 \times \text{BedAvailability} + 0.20 \times \text{DepartmentMatch} + 0.15 \times \text{IncomingDemand}$$

- Lower Hospital Cost indicates optimal transfer destination.
- Evaluates real-time ICU and Emergency bed availability; excludes hospitals on active diversion.

### 5. Swiggy-Style Live Ambulance Movement & Demo Mode

- **Demo Simulation Button**: "Load Emergency Simulation" loads a 5-incident concurrent scenario (A, B, C, D, E).
- **Smooth Trajectory Movement**: Ambulances smoothly animate along road coordinates with updating speed (44 km/h) and countdown ETA.
- **Route Segments**: Completed road segments show as a dimmed trailing line; remaining road segments show in vibrant blue.
- **Milestones**: Automatic on-scene arrival, patient pickup confirmation, dynamic route generation to destination hospital, and hospital handover completion.

---

## Repository

```text
frontend/       React/TypeScript/Vite UI, component and Playwright tests
backend/        FastAPI, SQLAlchemy, security, workflows, Alembic and Pytest
database/      ER diagram and integrity rules
infrastructure/ isolated test services and backup/restore scripts
docs/           architecture, API schema, verification results and screenshots
```

- [Architecture and security](docs/architecture.md)
- [Database design and ER diagram](database/README.md)
- [API guide](docs/api.md)
- [Verification and remaining deployment work](docs/verification.md)

## Local audit and corrections

See [local audit evidence](docs/LOCAL_AUDIT.md) for implemented fixes, verification commands, and remaining external-provider configuration. Browser-local incident substitutes and temporary SQLite fallback have been removed. `DATABASE_URL` and `SECRET_KEY` are required. Run `alembic upgrade head` before starting the API.

For a frontend running in a container, set `TERA_API_PROXY=http://host.containers.internal:8000`; on the host the default is `http://localhost:8000`. Use `http://localhost:5173` consistently with `PUBLIC_URL` so WebSocket Origin checks succeed.

Local evidence/audio fallback requires a persistent `RECORDINGS_DIR`. Compose mounts `/data/recordings` in a named volume. The audited Podman run uses the ignored `backend/.local/recordings` directory. SMTP is captured by Mailpit at http://localhost:8025. Google OAuth and speech/telephony require separately configured provider credentials; unavailable providers must not report fabricated success.

A provider key was present in the original source and has been removed from tracked code. Its owner should revoke that previously exposed key; deleting it from this checkout does not remove it from Git history.

### Voice agent configuration and verification

The local voice agent uses backend-only Sarvam speech credentials and an OpenRouter-compatible LLM (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`). See [the implementation and live verification record](docs/VOICE_AGENT_IMPLEMENTATION.md) for configuration, test evidence and acceptance limits. Source-based medical guidance remains English pending clinical review and reviewed translations.
