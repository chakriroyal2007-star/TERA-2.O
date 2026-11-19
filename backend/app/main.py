import uuid, time, json, os, logging
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text, select, func
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger("tera.access")
from .config import settings
from .db import engine
from .security import redis, roles
from . import auth, workflow, admin, realtime, evidence
from .speech import router as speech_router
from .companion.router import router as companion_router
from .dbms.router import router as dbms_router
from .routing.router import router as routing_router
from .optimization.router import router as optimization_router

app = FastAPI(title="TERA coordination API", version="2.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.on_event("startup")
def startup_event():
    import os
    if os.environ.get("TESTING") == "true":
        return
    try:
        from .db import engine, Base, SessionLocal
        from .bootstrap import bootstrap_defaults
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            bootstrap_defaults(db)
    except Exception as e:
        print("Startup bootstrap warning:", e)


# CORS setup
cors_origins_list = [o.strip() for o in settings().cors_origins.split(",") if o.strip()]
if settings().public_url not in cors_origins_list:
    cors_origins_list.append(settings().public_url)
if settings().environment != "production":
    for dev_port in ("5173", "5174", "5175", "8000", "8080", "3000"):
        for dev_host in ("localhost", "127.0.0.1"):
            dev_url = f"http://{dev_host}:{dev_port}"
            if dev_url not in cors_origins_list:
                cors_origins_list.append(dev_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings().secret_key,
    session_cookie="tera_oauth",
    https_only=False,
    same_site="lax",
    max_age=600,
)

modules = (auth, workflow, admin, realtime, evidence)
for module in modules:
    app.include_router(module.router, prefix="/api/v1")
    app.include_router(module.router, prefix="/api")

app.include_router(speech_router, prefix="/api/v1")
app.include_router(speech_router, prefix="/api")

app.include_router(companion_router, prefix="/api/v1")
app.include_router(companion_router, prefix="/api")

app.include_router(dbms_router, prefix="/api/v1")
app.include_router(dbms_router, prefix="/api")

app.include_router(routing_router, prefix="/api/v1")
app.include_router(routing_router, prefix="/api")

app.include_router(optimization_router, prefix="/api/v1")
app.include_router(optimization_router, prefix="/api")


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    t_start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id

    if not request.url.path.endswith(("/health", "/ready", "/metrics")):
        log_entry = {
            "timestamp": time.time(),
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        }
        logger.info(json.dumps(log_entry))
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 12 * 1024 * 1024:
                return JSONResponse({"detail": "Request payload exceeds maximum allowed size of 12MB"}, 413)
        except ValueError:
            pass

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin:
            allowed = [o.strip() for o in settings().cors_origins.split(",") if o.strip()]
            if settings().public_url not in allowed:
                allowed.append(settings().public_url)
            if settings().environment != "production":
                for dev_port in ("5173", "5174", "5175", "8000", "8080", "3000"):
                    for dev_host in ("localhost", "127.0.0.1"):
                        allowed.append(f"http://{dev_host}:{dev_port}")
                allowed.append("http://testserver")
            if origin not in allowed and not origin.endswith(".vercel.app"):
                return JSONResponse({"detail": "Origin not allowed"}, 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=(self)"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob: https://*.tile.openstreetmap.org https://tile.openstreetmap.org https://*.basemaps.cartocdn.com https://*.cartocdn.com https://unpkg.com; frame-ancestors 'none'; object-src 'none';"
    if settings().environment == "production" or settings().public_url.startswith("https://"):
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse({"detail": "This action conflicts with an existing record or resource assignment"}, 409)


@app.exception_handler(OperationalError)
async def database_unavailable(request, exc):
    return JSONResponse({"detail": "Database temporarily unavailable; please try again"}, 503)


@app.get("/api/health")
@app.get("/api/v1/health")
@app.get("/health")
def health():
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse({"status": "unavailable", "database": "unavailable", "error": str(exc)}, 503)
    rate_limiter = "redis"
    try:
        redis.ping()
    except Exception:
        rate_limiter = "in-memory"
    return {"status": "ok", "database": "connected", "rate_limiter": rate_limiter}


@app.get("/ready")
@app.get("/api/ready")
@app.get("/api/v1/ready")
def readiness_probe():
    checks = {}
    is_healthy = True

    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception as e:
        checks["database"] = f"down: {str(e)}"
        is_healthy = False

    try:
        redis.ping()
        checks["redis"] = "up"
    except Exception:
        checks["redis"] = "in-memory-fallback"

    try:
        storage_path = getattr(settings(), "recordings_dir", "/tmp/tera_recordings")
        os.makedirs(storage_path, exist_ok=True)
        test_file = os.path.join(storage_path, ".health_check")
        with open(test_file, "w") as f:
            f.write("ok")
        if os.path.exists(test_file):
            os.remove(test_file)
        checks["storage"] = "up"
    except Exception as e:
        checks["storage"] = f"down: {str(e)}"
        is_healthy = False

    status_code = 200 if is_healthy else 503
    return JSONResponse(
        {"status": "ready" if is_healthy else "degraded", "checks": checks},
        status_code=status_code,
    )


@app.get("/metrics")
@app.get("/api/metrics")
@app.get("/api/v1/metrics")
def prometheus_metrics():
    from .models import Incident, Mission, Ambulance
    from .db import SessionLocal
    try:
        with SessionLocal() as db:
            total_incidents = db.scalar(select(func.count()).select_from(Incident)) or 0
            active_missions = db.scalar(
                select(func.count()).select_from(Mission).where(~Mission.status.in_(["completed", "cancelled"]))
            ) or 0
            total_ambulances = db.scalar(select(func.count()).select_from(Ambulance)) or 0
    except Exception:
        total_incidents = 0
        active_missions = 0
        total_ambulances = 0

    lines = [
        "# HELP tera_incidents_total Total number of emergency incidents reported.",
        "# TYPE tera_incidents_total counter",
        f"tera_incidents_total {total_incidents}",
        "# HELP tera_active_missions Current active dispatched emergency missions.",
        "# TYPE tera_active_missions gauge",
        f"tera_active_missions {active_missions}",
        "# HELP tera_fleet_total Total registered ambulances in fleet.",
        "# TYPE tera_fleet_total gauge",
        f"tera_fleet_total {total_ambulances}",
        "# HELP tera_service_health Service up indicator.",
        "# TYPE tera_service_health gauge",
        "tera_service_health 1",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/api/v1/system")
def system(user=Depends(roles("admin"))):
    return {
        "health": (result if isinstance(result := health(), dict) else {"status": "unavailable"}),
        "email_host_configured": bool(settings().smtp_host),
        "google_configured": settings().google_configured,
        "mfa_required_privileged": settings().mfa_required_privileged,
        "environment": settings().environment,
    }
