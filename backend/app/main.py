from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from .config import settings
from .db import engine
from .security import redis, roles
from . import auth, workflow, admin, realtime, evidence
from .speech import router as speech_router
from .companion.router import router as companion_router
from .dbms.router import router as dbms_router

app = FastAPI(title="TERA coordination API", version="2.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

# CORS setup
cors_origins_list = [o.strip() for o in settings().cors_origins.split(",") if o.strip()]
if settings().public_url not in cors_origins_list:
    cors_origins_list.append(settings().public_url)

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


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin:
            allowed = [o.strip() for o in settings().cors_origins.split(",") if o.strip()]
            if settings().public_url not in allowed:
                allowed.append(settings().public_url)
            if settings().environment != "production":
                allowed.extend([
                    "http://localhost:8080",
                    "http://localhost:5173",
                    "http://localhost:8000",
                    "http://localhost:3000",
                    "http://127.0.0.1:8080",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:8000",
                    "http://testserver",
                ])
            if origin not in allowed and not origin.endswith(".vercel.app"):
                return JSONResponse({"detail": "Origin not allowed"}, 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
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


@app.get("/api/v1/system")
def system(user=Depends(roles("admin"))):
    return {
        "health": (result if isinstance(result := health(), dict) else {"status": "unavailable"}),
        "email_host_configured": bool(settings().smtp_host),
        "google_configured": settings().google_configured,
        "mfa_required_privileged": settings().mfa_required_privileged,
        "environment": settings().environment,
    }
