import os

os.environ["SHIFTGENIE_TEST_DB"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import crud, models, schemas
from backend.database import Base

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_employee_in(**overrides):
    data = {
        "name": "Test Employee",
        "role": "Cashier",
        "max_weekly_hours": 30,
        "preferred_shift": "Morning",
        "skills": ["Cash Handling"],
        "certifications": [
            {"name": "Food Safety", "verification_status": "verified", "verification_source": "State Board"}
        ],
        "availability": [{"day_of_week": "Monday", "start_time": "09:00", "end_time": "17:00"}],
    }
    data.update(overrides)
    return schemas.EmployeeIn(**data)


def test_tables_created(db):
    table_names = Base.metadata.tables.keys()
    for expected in ["employees", "skills", "certifications", "availabilities", "shifts"]:
        assert expected in table_names


def test_create_employee(db):
    employee = crud.create_employee(db, make_employee_in())
    assert employee.id is not None
    assert employee.name == "Test Employee"
    assert len(employee.skills) == 1
    assert len(employee.certifications) == 1
    assert len(employee.availabilities) == 1


def test_get_employees(db):
    crud.create_employee(db, make_employee_in(name="Alice"))
    crud.create_employee(db, make_employee_in(name="Bob"))
    employees = crud.get_employees(db)
    assert len(employees) == 2


def test_update_employee(db):
    employee = crud.create_employee(db, make_employee_in())
    updated = crud.update_employee(
        db, employee, make_employee_in(name="Updated Name", max_weekly_hours=20)
    )
    assert updated.name == "Updated Name"
    assert updated.max_weekly_hours == 20


def test_delete_employee(db):
    employee = crud.create_employee(db, make_employee_in())
    emp_id = employee.id
    crud.delete_employee(db, employee)
    assert crud.get_employee(db, emp_id) is None


def test_certification_verification_status(db):
    employee = crud.create_employee(
        db,
        make_employee_in(
            certifications=[
                {"name": "First Aid", "verification_status": "expired", "verification_source": "Red Cross"}
            ]
        ),
    )
    cert = employee.certifications[0]
    assert cert.verification_status == "expired"

    verified_only = [c for c in employee.certifications if c.verification_status == "verified"]
    assert verified_only == []
