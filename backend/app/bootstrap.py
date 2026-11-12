import uuid
from sqlalchemy import select
from . import models as m
from .security import passwords


def deterministic_id(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://tera.org/{key}"))


DEMO_USERS = [
    ("beesvenkatrahul@gmail.com", "Venkat Rahul", "admin", "Emergency@2025!"),
    ("chakriroyal2007@gmail.com", "Chakri", "admin", "Emergency@2025!"),
    ("admin@tera.org", "System Administrator", "admin", "Emergency@2025!"),
    ("operator@tera.org", "Control Operator", "operator", "Emergency@2025!"),
    ("hospital@tera.org", "Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("responder@tera.org", "Field Responder", "responder", "Emergency@2025!"),
    ("analyst@tera.org", "Operational Analyst", "analyst", "Emergency@2025!"),
    ("admin@tera.local", "Local Administrator", "admin", "Admin@12345678"),
]


def bootstrap_defaults(db):
    """Seed base roles, primary organizations, pre-configured admin and demo staff accounts,

    hospitals, and ambulances with consistent deterministic IDs across all environments.
    """
    try:
        # 1. Seed Roles
        for role_id in ["citizen", "operator", "hospital", "responder", "analyst", "admin"]:
            if not db.get(m.Role, role_id):
                db.add(m.Role(id=role_id, name=role_id.title()))
        db.flush()

        # 2. Seed Primary Organizations
        eoc_id = deterministic_id("org:eoc")
        org = db.get(m.Organization, eoc_id)
        if not org:
            org = db.scalar(select(m.Organization).where(m.Organization.name == "Emergency Operations Center"))
        if not org:
            org = m.Organization(id=eoc_id, name="Emergency Operations Center")
            db.add(org)
            db.flush()

        hosp_net_id = deterministic_id("org:hospital-network")
        horg = db.get(m.Organization, hosp_net_id)
        if not horg:
            horg = db.scalar(select(m.Organization).where(m.Organization.name == "City Emergency Hospital Network"))
        if not horg:
            horg = m.Organization(id=hosp_net_id, name="City Emergency Hospital Network")
            db.add(horg)
            db.flush()

        # 3. Seed Users (Admins & Demo Accounts)
        for email, name, role, pw in DEMO_USERS:
            target_org_id = horg.id if role == "hospital" else org.id
            uid = deterministic_id(f"user:{email.lower()}")
            u = db.get(m.User, uid)
            if not u:
                u = db.scalar(select(m.User).where(m.User.email == email.lower()))
            if not u:
                u = m.User(
                    id=uid,
                    email=email.lower(),
                    name=name,
                    password_hash=passwords.hash(pw),
                    verified=True,
                    role=role,
                    organization_id=target_org_id,
                    suspended=False,
                )
                db.add(u)
            else:
                u.role = role
                u.verified = True
                u.suspended = False
                u.password_hash = passwords.hash(pw)
                if not u.organization_id:
                    u.organization_id = target_org_id
        db.flush()

        # 4. Seed Hospital & Capacities
        hosp_id = deterministic_id("hospital:city-central")
        h = db.get(m.Hospital, hosp_id)
        if not h:
            h = db.scalar(select(m.Hospital).where(m.Hospital.name == "City Central Emergency Hospital"))
        if not h:
            h = m.Hospital(
                id=hosp_id,
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
        db.flush()

        # 5. Seed Ambulances
        if not db.scalar(select(m.Ambulance).where(m.Ambulance.registration == "TERA-AMB-01")):
            db.add(m.Ambulance(organization_id=org.id, registration="TERA-AMB-01", active=True))
        if not db.scalar(select(m.Ambulance).where(m.Ambulance.registration == "TERA-AMB-02")):
            db.add(m.Ambulance(organization_id=org.id, registration="TERA-AMB-02", active=True))

        db.commit()
    except Exception as e:
        db.rollback()
        print("Bootstrap warning:", e)
