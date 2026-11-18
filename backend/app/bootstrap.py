import uuid
from sqlalchemy import select
from . import models as m
from .security import passwords


def deterministic_id(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://tera.org/{key}"))


DEMO_USERS = [
    # Primary Admin & Operator Personal Accounts
    ("beesvenkatrahul@gmail.com", "Venkat Rahul", "admin", "Emergency@2025!"),
    ("chakriroyal2007@gmail.com", "Chakri", "admin", "Emergency@2025!"),
    ("venkatrahul2003@gmail.com", "Venkat Rahul", "operator", "Emergency@2025!"),
    # Standard Role Accounts (@tera.org)
    ("admin@tera.org", "System Administrator", "admin", "Emergency@2025!"),
    ("operator@tera.org", "Control Operator", "operator", "Emergency@2025!"),
    ("hospital@tera.org", "Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.city@tera.org", "City Central Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.apollo@tera.org", "Apollo Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.manipal@tera.org", "Manipal Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.fortis@tera.org", "Fortis Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.rainbow@tera.org", "Rainbow Children's Coordinator", "hospital", "Emergency@2025!"),
    ("coordinator.stjohns@tera.org", "St. John's Coordinator", "hospital", "Emergency@2025!"),
    ("responder@tera.org", "Field Responder", "responder", "Emergency@2025!"),
    ("responder2@tera.org", "Field Responder Bravo", "responder", "Emergency@2025!"),
    ("analyst@tera.org", "Operational Analyst", "analyst", "Emergency@2025!"),
    ("citizen@tera.org", "Citizen Reporter", "citizen", "Emergency@2025!"),
    ("admin@tera.local", "Local Administrator", "admin", "Admin@12345678"),
    # Demo/Eval Role Accounts (@example.com)
    ("admin@example.com", "System Administrator", "admin", "Emergency@2025!"),
    ("operator@example.com", "Control Operator", "operator", "Emergency@2025!"),
    ("hospital@example.com", "Hospital Coordinator", "hospital", "Emergency@2025!"),
    ("responder@example.com", "Field Responder", "responder", "Emergency@2025!"),
    ("analyst@example.com", "Operational Analyst", "analyst", "Emergency@2025!"),
    ("citizen@example.com", "Citizen Reporter", "citizen", "Emergency@2025!"),
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
        # 4. Seed 6 Comprehensive Multi-Specialty Hospitals
        hospitals_seed = [
            {
                "id": deterministic_id("hospital:city-central"),
                "name": "City Central Emergency Hospital",
                "hospital_type": "Level-1 Apex Trauma Center",
                "phone": "+91 80 2299 1000",
                "emergency_phone": "112 / 108",
                "address": "100 Emergency Care Blvd, Sampangi Rama Nagar",
                "city": "Bengaluru",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "specialties": ["Trauma care", "Surgery", "Cardiac care", "ICU", "Ventilator", "Blood bank", "Emergency trauma support", "ICU support"],
                "facilities": ["24/7 Trauma Bay", "Cath Lab", "Blood Bank", "CT/MRI Imaging", "Helipad Resuscitation"],
                "departments": [
                    ("Emergency & Resuscitation", [("icu", 25, 6, 2, 0), ("emergency", 40, 12, 3, 0)]),
                    ("Cardiology & CCU", [("icu", 15, 5, 1, 0), ("general", 20, 8, 2, 0)]),
                    ("Surgical Trauma", [("icu", 15, 4, 1, 0), ("emergency", 20, 6, 2, 0)]),
                ]
            },
            {
                "id": deterministic_id("hospital:apollo-multi"),
                "name": "Apollo Multi-Specialty Hospital",
                "hospital_type": "Apex Super-Specialty & Level-1 Trauma",
                "phone": "+91 80 2630 4050",
                "emergency_phone": "1066",
                "address": "154/11 Bannerghatta Road, Opp IIMB",
                "city": "Bengaluru",
                "latitude": 12.8958,
                "longitude": 77.5992,
                "specialties": ["Trauma care", "Surgery", "Cardiac care", "ICU", "Ventilator", "Blood bank", "Burns treatment", "Neurology", "Emergency trauma support"],
                "facilities": ["Dedicated Burn ICU", "Advanced Stroke Center", "Organ Transplant Unit", "24/7 Dialysis", "Blood Bank"],
                "departments": [
                    ("Emergency Trauma Bay", [("emergency", 35, 10, 2, 0), ("icu", 20, 5, 2, 0)]),
                    ("Neuro & Spine Critical Care", [("icu", 16, 4, 1, 0), ("emergency", 12, 3, 1, 0)]),
                    ("Burns Care Unit", [("icu", 10, 2, 1, 0), ("general", 15, 4, 1, 0)]),
                ]
            },
            {
                "id": deterministic_id("hospital:manipal-trauma"),
                "name": "Manipal Emergency & Trauma Center",
                "hospital_type": "Multi-Specialty Trauma Care & Orthopedics",
                "phone": "+91 80 2502 4444",
                "emergency_phone": "080-2502-3333",
                "address": "98 HAL Airport Road, Kodihalli",
                "city": "Bengaluru",
                "latitude": 12.9592,
                "longitude": 77.6534,
                "specialties": ["Trauma care", "Surgery", "ICU", "Ventilator", "Blood bank", "Orthopedics", "Emergency trauma support", "ICU support"],
                "facilities": ["Polytrauma Resuscitation", "High-Velocity Collision Theater", "Blood Bank", "Robotic Surgical Bay"],
                "departments": [
                    ("Polytrauma & Emergency", [("emergency", 30, 8, 2, 0), ("icu", 18, 6, 2, 0)]),
                    ("Orthopedic Critical Care", [("general", 25, 9, 2, 0), ("icu", 10, 3, 1, 0)]),
                ]
            },
            {
                "id": deterministic_id("hospital:fortis-stroke"),
                "name": "Fortis Healthcare Super-Specialty",
                "hospital_type": "Comprehensive Stroke & Cardiac Center",
                "phone": "+91 80 6621 4444",
                "emergency_phone": "105711",
                "address": "14 Cunningham Road, Vasanth Nagar",
                "city": "Bengaluru",
                "latitude": 12.9868,
                "longitude": 77.5998,
                "specialties": ["Cardiac care", "Stroke care", "ICU", "Ventilator", "Neurology", "Blood bank", "Surgery"],
                "facilities": ["Rapid Stroke Thrombolysis Unit", "Emergency Cath Lab", "ECMO Support", "24/7 CCU"],
                "departments": [
                    ("Comprehensive Stroke Center", [("icu", 14, 4, 1, 0), ("emergency", 20, 6, 2, 0)]),
                    ("Cardiovascular Emergency", [("icu", 16, 5, 2, 0), ("general", 22, 7, 2, 0)]),
                ]
            },
            {
                "id": deterministic_id("hospital:rainbow-children"),
                "name": "Rainbow Children's Emergency Hospital",
                "hospital_type": "Paediatric Emergency & Neonatal Center",
                "phone": "+91 80 4241 2345",
                "emergency_phone": "080-4241-0000",
                "address": "Survey No. 8/5 Marathahalli - Sarjapur Road",
                "city": "Bengaluru",
                "latitude": 12.9248,
                "longitude": 77.6749,
                "specialties": ["Paediatric emergency care", "Paediatric surgery", "NICU", "PICU", "Ventilator", "Blood bank"],
                "facilities": ["Level-4 NICU", "Paediatric Trauma Bay", "Dedicated Paediatric Ambulance Transfer", "Child Life Specialists"],
                "departments": [
                    ("Paediatric Emergency (ER)", [("emergency", 25, 6, 2, 0), ("icu", 18, 5, 2, 0)]),
                    ("Neonatal Critical Care (NICU)", [("icu", 22, 7, 2, 0), ("general", 15, 3, 1, 0)]),
                ]
            },
            {
                "id": deterministic_id("hospital:st-johns"),
                "name": "St. John's Medical College Hospital",
                "hospital_type": "Government-Affiliated Teaching Trauma Center",
                "phone": "+91 80 4946 6000",
                "emergency_phone": "080-2206-5000",
                "address": "Sarjapur Road, John Nagar, Koramangala",
                "city": "Bengaluru",
                "latitude": 12.9344,
                "longitude": 77.6189,
                "specialties": ["Trauma care", "Surgery", "Burns treatment", "Blood bank", "ICU support", "Paediatric emergency care", "General emergency"],
                "facilities": ["Mass Casualty Triage Yard", "24/7 Red Cross Blood Bank", "Toxicology & Poison Control", "Burns Ward"],
                "departments": [
                    ("Central Emergency Casualty", [("emergency", 45, 14, 4, 0), ("icu", 25, 8, 3, 0)]),
                    ("Burns & Plastic Surgery ICU", [("icu", 12, 3, 1, 0), ("emergency", 15, 4, 2, 0)]),
                    ("General Medical Critical Care", [("general", 30, 10, 3, 0), ("icu", 15, 5, 2, 0)]),
                ]
            },
        ]

        for hdata in hospitals_seed:
            h = db.get(m.Hospital, hdata["id"]) or db.scalar(select(m.Hospital).where(m.Hospital.name == hdata["name"]))
            if not h:
                h = m.Hospital(
                    id=hdata["id"],
                    name=hdata["name"],
                    organization_id=horg.id,
                    hospital_type=hdata["hospital_type"],
                    address=hdata["address"],
                    city=hdata["city"],
                    phone=hdata["phone"],
                    emergency_phone=hdata["emergency_phone"],
                    operating_status="Operational",
                    verification_status="approved",
                    latitude=hdata["latitude"],
                    longitude=hdata["longitude"],
                    specialties=hdata["specialties"],
                    facilities=hdata["facilities"],
                    diversion_status=False,
                )
                db.add(h)
                db.flush()
            else:
                h.phone = hdata["phone"]
                h.emergency_phone = hdata["emergency_phone"]
                h.address = hdata["address"]
                h.latitude = hdata["latitude"]
                h.longitude = hdata["longitude"]
                h.specialties = hdata["specialties"]
                h.facilities = hdata["facilities"]
                h.operating_status = "Operational"
                h.verification_status = "approved"

            for dept_name, capacities in hdata["departments"]:
                dept = db.scalar(select(m.Department).where(m.Department.hospital_id == h.id, m.Department.name == dept_name))
                if not dept:
                    dept = m.Department(hospital_id=h.id, name=dept_name, dept_type="Emergency")
                    db.add(dept)
                    db.flush()
                for kind, total, occ, res, oos in capacities:
                    cap = db.scalar(select(m.Capacity).where(m.Capacity.department_id == dept.id, m.Capacity.kind == kind))
                    if not cap:
                        cap = m.Capacity(department_id=dept.id, kind=kind, total=total, occupied=occ, reserved=res, out_of_service=oos)
                        db.add(cap)
                    else:
                        cap.total = total
                        cap.occupied = occ
                        cap.reserved = res
                        cap.out_of_service = oos
        db.flush()

        # 5. Seed 8 Ambulances with complete driver and vehicle details
        ambulances_seed = [
            ("TERA-AMB-01", "Advanced Life Support (ALS)", "Suresh Varma", "+91 98491 10801"),
            ("TERA-AMB-02", "Advanced Life Support (ALS)", "Ramesh Kumar (Pilot)", "+91 98490 12345"),
            ("TERA-AMB-03", "Basic Life Support (BLS)", "K. Praveen", "+91 98492 10803"),
            ("TERA-AMB-04", "Critical Care Transport (CCT)", "M. Srinivas", "+91 98493 10804"),
            ("TERA-AMB-05", "Advanced Life Support (ALS)", "Abdul Rahim", "+91 98494 10805"),
            ("TERA-AMB-06", "Paediatric / Neonatal Unit", "T. Rajesh", "+91 98495 10806"),
            ("TERA-AMB-07", "Rapid Response Paramedic Unit", "Anil Sharma", "+91 98496 10807"),
            ("TERA-AMB-08", "Advanced Cardiac Life Support (ACLS)", "Vikram Reddy", "+91 98497 10808"),
        ]

        for idx, (amb_reg, vtype, driver, phone) in enumerate(ambulances_seed):
            amb = db.scalar(select(m.Ambulance).where(m.Ambulance.registration == amb_reg))
            lat_offset = 13.6250 + (idx * 0.006)
            lng_offset = 79.4150 + (idx * 0.005)
            cap = 2 if "Basic" not in vtype else 1
            eq = "ALS" if "Advanced" in vtype or "Cardiac" in vtype else "BLS"
            if not amb:
                db.add(m.Ambulance(
                    organization_id=org.id,
                    registration=amb_reg,
                    vehicle_type=vtype,
                    driver_name=driver,
                    driver_phone=phone,
                    patient_capacity=cap,
                    equipment_level=eq,
                    current_latitude=lat_offset,
                    current_longitude=lng_offset,
                    current_speed=0.0,
                    active=True,
                ))
            else:
                amb.vehicle_type = vtype
                amb.driver_name = driver
                amb.driver_phone = phone
                amb.active = True
                amb.patient_capacity = cap
                amb.equipment_level = eq
                if amb.current_latitude is None:
                    amb.current_latitude = lat_offset
                    amb.current_longitude = lng_offset
                    amb.current_speed = 0.0

        # 6. Associate Users (Coordinators & Responders) and Ambulances to Specific Hospitals
        h_city = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "City Central Emergency Hospital"))
        h_apollo = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "Apollo Multi-Specialty Hospital"))
        h_manipal = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "Manipal Emergency & Trauma Center"))
        h_fortis = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "Fortis Healthcare Super-Specialty"))
        h_rainbow = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "Rainbow Children's Emergency Hospital"))
        h_stjohns = db.scalar(select(m.Hospital.id).where(m.Hospital.name == "St. John's Medical College Hospital"))

        user_hosp_map = {
            "hospital@tera.org": h_city,
            "coordinator.city@tera.org": h_city,
            "coordinator.apollo@tera.org": h_apollo,
            "coordinator.manipal@tera.org": h_manipal,
            "coordinator.fortis@tera.org": h_fortis,
            "coordinator.rainbow@tera.org": h_rainbow,
            "coordinator.stjohns@tera.org": h_stjohns,
            "hospital@example.com": h_apollo,
            "responder@tera.org": h_city,
            "responder2@tera.org": h_city,
            "responder@example.com": h_city,
            "responder3@tera.org": h_apollo,
            "responder4@tera.org": h_apollo,
            "responder5@tera.org": h_manipal,
            "responder6@tera.org": h_manipal,
            "responder7@tera.org": h_fortis,
            "responder8@tera.org": h_fortis,
        }

        for uemail, hid in user_hosp_map.items():
            u = db.scalar(select(m.User).where(m.User.email == uemail.lower()))
            if u:
                u.hospital_id = hid

        amb_hosp_map = {
            "TERA-AMB-01": h_city,
            "TERA-AMB-02": h_city,
            "TERA-AMB-03": h_apollo,
            "TERA-AMB-04": h_apollo,
            "TERA-AMB-05": h_manipal,
            "TERA-AMB-06": h_manipal,
            "TERA-AMB-07": h_fortis,
            "TERA-AMB-08": h_stjohns,
        }

        for reg, hid in amb_hosp_map.items():
            amb = db.scalar(select(m.Ambulance).where(m.Ambulance.registration == reg))
            if amb:
                amb.hospital_id = hid

        db.commit()
    except Exception as e:
        db.rollback()
        print("Bootstrap warning:", e)


def main():
    """Interactive administrator bootstrap; creates no demonstration or operational records."""
    import getpass
    from sqlalchemy import select, text
    from pydantic import TypeAdapter, EmailStr
    from .db import SessionLocal
    from .models import User, Organization
    from .security import passwords, audit

    email = TypeAdapter(EmailStr).validate_python(input("Administrator email: ").strip()).lower()
    name = input("Administrator name: ").strip()
    organization = input("Control organization name: ").strip()
    password = getpass.getpass("Password (12+ characters): ")
    if len(password) < 12 or not name or not organization:
        raise SystemExit("Name, organization and a strong password are required")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    with SessionLocal() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(84637202)"))
        if db.scalar(select(User.id).where(User.role == "admin")):
            raise SystemExit("An administrator already exists; use invitations")
        org = Organization(name=organization)
        db.add(org)
        db.flush()
        u = User(
            email=email,
            name=name,
            password_hash=passwords.hash(password),
            role="admin",
            verified=True,
            organization_id=org.id,
        )
        db.add(u)
        db.flush()
        audit(db, "admin.bootstrapped", u.id, u)
        db.commit()
    print("Administrator created. Sign in to invite operational staff and register resources.")


if __name__ == "__main__":
    main()

