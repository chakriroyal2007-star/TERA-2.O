"""Serverless entry point for Vercel deployment."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db import engine, Base, SessionLocal
import app.models  # Register all models on Base.metadata
from app.bootstrap import bootstrap_defaults
from app.companion.knowledge import seed_emergency_knowledge

# 1. Initialize Tables
try:
    Base.metadata.create_all(engine)
except Exception as e:
    print("Table creation warning:", e)

# 2. Seed Default Roles, Organizations, Staff, Facilities & Emergency Protocols
try:
    with SessionLocal() as db:
        bootstrap_defaults(db)
        seed_emergency_knowledge(db)
except Exception as e:
    print("Bootstrap seed warning:", e)

from app.main import app
