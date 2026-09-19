"""Database operations for employees and shifts."""

from sqlalchemy.orm import Session, selectinload

from backend import models, schemas


def _get_or_create_skill(db: Session, name: str) -> models.Skill:
    skill = db.query(models.Skill).filter(models.Skill.name == name).first()
    if not skill:
        skill = models.Skill(name=name)
        db.add(skill)
        db.flush()
    return skill


def _make_certification(cert: schemas.CertificationIn) -> models.Certification:
    # Each employee's certification is its own record: verification status
    # (verified/unverified/expired) is per person, not shared by name.
    return models.Certification(
        name=cert.name,
        verification_status=cert.verification_status,
        verification_source=cert.verification_source,
    )


def create_employee(db: Session, data: schemas.EmployeeIn) -> models.Employee:
    employee = models.Employee(
        name=data.name,
        role=data.role,
        max_weekly_hours=data.max_weekly_hours,
        preferred_shift=data.preferred_shift,
    )
    db.add(employee)
    employee.skills = [_get_or_create_skill(db, s) for s in data.skills]
    employee.certifications = [
        _make_certification(c) for c in data.certifications
    ]
    employee.availabilities = [
        models.Availability(
            day_of_week=a.day_of_week, start_time=a.start_time, end_time=a.end_time
        )
        for a in data.availability
    ]
    db.commit()
    db.refresh(employee)
    return employee


def get_employees(db: Session):
    return (
        db.query(models.Employee)
        .options(
            selectinload(models.Employee.skills),
            selectinload(models.Employee.certifications),
            selectinload(models.Employee.availabilities),
        )
        .all()
    )


def get_employee(db: Session, employee_id: int):
    return db.query(models.Employee).filter(models.Employee.id == employee_id).first()


def update_employee(db: Session, employee: models.Employee, data: schemas.EmployeeIn):
    employee.name = data.name
    employee.role = data.role
    employee.max_weekly_hours = data.max_weekly_hours
    employee.preferred_shift = data.preferred_shift
    employee.skills = [_get_or_create_skill(db, s) for s in data.skills]
    employee.certifications = [
        _make_certification(c) for c in data.certifications
    ]
    for old in list(employee.availabilities):
        db.delete(old)
    employee.availabilities = [
        models.Availability(
            day_of_week=a.day_of_week, start_time=a.start_time, end_time=a.end_time
        )
        for a in data.availability
    ]
    db.commit()
    db.refresh(employee)
    return employee


def delete_employee(db: Session, employee: models.Employee):
    db.delete(employee)
    db.commit()


def shift_to_out(shift: models.Shift) -> schemas.ShiftOut:
    return schemas.ShiftOut(
        id=shift.id,
        name=shift.name,
        day_of_week=shift.day_of_week,
        start_time=shift.start_time,
        end_time=shift.end_time,
        required_staff=shift.required_staff,
        required_roles=shift.required_roles.split(",") if shift.required_roles else [],
        required_certifications=(
            shift.required_certifications.split(",")
            if shift.required_certifications
            else []
        ),
    )


def create_shift(db: Session, data: schemas.ShiftIn) -> models.Shift:
    shift = models.Shift(
        name=data.name,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        required_staff=data.required_staff,
        required_roles=",".join(data.required_roles),
        required_certifications=",".join(data.required_certifications),
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def get_shifts(db: Session):
    return db.query(models.Shift).all()
