"""Load sample_data/demo_scenario.json into the database, skipping records that
already exist so re-loading never duplicates or destroys user-created data.

Run standalone with: python -m backend.load_demo_data
Or via the API: POST /demo/load (used by the frontend's "Load Demo Scenario" button)
"""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend import crud, models, schemas
from backend.database import Base, SessionLocal, engine

DEMO_FILE = Path(__file__).resolve().parent.parent / "sample_data" / "demo_scenario.json"


def load_demo_data(db: Session) -> dict:
    data = json.loads(DEMO_FILE.read_text())

    employees_added = 0
    for emp in data["employees"]:
        exists = db.query(models.Employee).filter(models.Employee.name == emp["name"]).first()
        if exists:
            continue
        crud.create_employee(db, schemas.EmployeeIn(**emp))
        employees_added += 1

    shifts_added = 0
    for shift in data.get("shifts", []):
        exists = (
            db.query(models.Shift)
            .filter(models.Shift.name == shift["name"], models.Shift.day_of_week == shift["day_of_week"])
            .first()
        )
        if exists:
            continue
        crud.create_shift(db, schemas.ShiftIn(**shift))
        shifts_added += 1

    return {
        "scenario_label": data.get("scenario_label", "Demo Scenario"),
        "employees_added": employees_added,
        "employees_skipped": len(data["employees"]) - employees_added,
        "shifts_added": shifts_added,
        "shifts_skipped": len(data.get("shifts", [])) - shifts_added,
    }


def _sig_in(e: schemas.EmployeeIn) -> tuple:
    return (
        e.role, e.max_weekly_hours, e.preferred_shift or None, tuple(sorted(e.skills)),
        tuple(sorted((c.name, c.verification_status, c.verification_source or None) for c in e.certifications)),
        tuple(sorted((a.day_of_week, a.start_time, a.end_time) for a in e.availability)),
    )


def _sig_db(e: models.Employee) -> tuple:
    return (
        e.role, e.max_weekly_hours, e.preferred_shift or None, tuple(sorted(s.name for s in e.skills)),
        tuple(sorted((c.name, c.verification_status, c.verification_source or None) for c in e.certifications)),
        tuple(sorted((a.day_of_week, a.start_time, a.end_time) for a in e.availabilities)),
    )


def reset_demo_data(db: Session) -> dict:
    """Restore the synthetic demo workforce/shifts to the baseline in sample_data. Only records
    that belong to the demo (matched by name) are touched; user-created employees are left alone."""
    data = json.loads(DEMO_FILE.read_text())
    existing = {e.name: e for e in crud.get_employees(db)}
    added = restored = 0
    for emp in data["employees"]:
        payload = schemas.EmployeeIn(**emp)
        current = existing.get(emp["name"])
        if current is None:
            crud.create_employee(db, payload)
            added += 1
        elif _sig_db(current) != _sig_in(payload):
            crud.update_employee(db, current, payload)
            restored += 1

    shifts_added = shifts_restored = 0
    for sh in data.get("shifts", []):
        payload = schemas.ShiftIn(**sh)
        row = (
            db.query(models.Shift)
            .filter(models.Shift.name == payload.name, models.Shift.day_of_week == payload.day_of_week)
            .first()
        )
        roles, certs = ",".join(payload.required_roles), ",".join(payload.required_certifications)
        if row is None:
            crud.create_shift(db, payload)
            shifts_added += 1
        elif (row.start_time, row.end_time, row.required_staff, row.required_roles or "", row.required_certifications or "") != (
            payload.start_time, payload.end_time, payload.required_staff, roles, certs
        ):
            row.start_time, row.end_time, row.required_staff = payload.start_time, payload.end_time, payload.required_staff
            row.required_roles, row.required_certifications = roles, certs
            db.commit()
            shifts_restored += 1
    return {
        "scenario_label": data.get("scenario_label", "Demo Scenario"),
        "employees_added": added, "employees_restored": restored,
        "shifts_added": shifts_added, "shifts_restored": shifts_restored,
    }


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        print(load_demo_data(session))
    finally:
        session.close()
