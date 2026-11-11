"""Serverless entry point for Vercel deployment."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db import engine, Base, SessionLocal
import app.models as m
from app.security import passwords

# 1. Initialize Tables
try:
    Base.metadata.create_all(engine)
except Exception as e:
    print("Table creation warning:", e)

# 2. Seed Default Roles, Organizations, Demo Staff & Facilities
try:
    with SessionLocal() as db:
        # Seed Roles
        for role_id in ["citizen", "operator", "hospital", "responder", "analyst", "admin"]:
            if not db.get(m.Role, role_id):
                db.add(m.Role(id=role_id, name=role_id.title()))
        db.flush()

        # Seed Organizations
        org = db.query(m.Organization).filter_by(name="Emergency Operations Center").first()
        if not org:
            org = m.Organization(name="Emergency Operations Center")
            db.add(org)
            db.flush()

        horg = db.query(m.Organization).filter_by(name="City Emergency Hospital Network").first()
        if not horg:
            horg = m.Organization(name="City Emergency Hospital Network")
            db.add(horg)
            db.flush()

        # Seed Demo Accounts for Instant Quick-Launch
        demo_users = [
            ("admin@tera.org", "System Administrator", "admin", "Emergency@2025!", org.id),
            ("operator@tera.org", "Control Operator", "operator", "Emergency@2025!", org.id),
            ("hospital@tera.org", "Hospital Coordinator", "hospital", "Emergency@2025!", horg.id),
            ("responder@tera.org", "Field Responder", "responder", "Emergency@2025!", org.id),
            ("analyst@tera.org", "Operational Analyst", "analyst", "Emergency@2025!", org.id),
            ("admin@tera.local", "Local Administrator", "admin", "Admin@12345678", org.id),
        ]
        for email, name, role, pw, oid in demo_users:
            if not db.query(m.User).filter_by(email=email).first():
                db.add(
                    m.User(
                        email=email,
                        name=name,
                        password_hash=passwords.hash(pw),
                        verified=True,
                        role=role,
                        organization_id=oid,
                    )
                )
        db.flush()

        # Seed Demo Hospital & Emergency Capacity
        h = db.query(m.Hospital).filter_by(name="City Central Emergency Hospital").first()
        if not h:
            h = m.Hospital(
                name="City Central Emergency Hospital",
                organization_id=horg.id,
                hospital_type="Level 1 Trauma Center",
                address="100 Emergency Care Blvd",
                city="Metro City",
                emergency_phone="112",
                operating_status="Operational",
                verification_status="approved",
                latitude=12.9716,
                longitude=77.5946,
            )
            db.add(h)
            db.flush()
            dept = m.Department(hospital_id=h.id, name="Emergency & Trauma", dept_type="Emergency")
            db.add(dept)
            db.flush()
            db.add(m.Capacity(department_id=dept.id, kind="icu", total=20, occupied=8, reserved=2, out_of_service=0))
            db.add(m.Capacity(department_id=dept.id, kind="emergency", total=40, occupied=15, reserved=3, out_of_service=0))

        # Seed Demo Ambulances
        if not db.query(m.Ambulance).filter_by(registration="TERA-AMB-01").first():
            db.add(m.Ambulance(organization_id=org.id, registration="TERA-AMB-01", active=True))
            db.add(m.Ambulance(organization_id=org.id, registration="TERA-AMB-02", active=True))

        db.commit()
except Exception as e:
    print("Bootstrap seed warning:", e)

from app.main import app
