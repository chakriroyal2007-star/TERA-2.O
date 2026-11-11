"""Serverless entry point."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db import engine, Base, SessionLocal
import app.models  # ensure models are registered
try:
    Base.metadata.create_all(engine)
except Exception:
    pass

try:
    from sqlalchemy import select
    from app.models import User, Organization
    from app.security import passwords
    with SessionLocal() as db:
        if not db.scalar(select(User.id).where(User.role == "admin")):
            org = Organization(name="Emergency Operations Center")
            db.add(org)
            db.flush()
            admin_user = User(
                email="admin@tera.local",
                name="System Administrator",
                password_hash=passwords.hash("Admin@12345678"),
                role="admin",
                verified=True,
                organization_id=org.id,
            )
            db.add(admin_user)
            db.commit()
except Exception:
    pass

from app.main import app
