"""Serverless entry point for Vercel deployment."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db import engine, Base, SessionLocal
from app.bootstrap import bootstrap_defaults

# 1. Initialize Tables
try:
    Base.metadata.create_all(engine)
except Exception as e:
    print("Table creation warning:", e)

# 2. Seed Default Roles, Organizations, Staff & Facilities
try:
    with SessionLocal() as db:
        bootstrap_defaults(db)
except Exception as e:
    print("Bootstrap seed warning:", e)

from app.main import app
