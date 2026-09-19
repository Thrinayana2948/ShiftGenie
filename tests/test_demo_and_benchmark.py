import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import crud, schemas
from backend.database import Base
from backend.load_demo_data import load_demo_data
from backend.services.benchmark_adapter import load_benchmark_instance
from backend.services.scheduler import generate_schedule
from backend.services.scheduler_types import from_db
from backend.services.validator import validate_schedule

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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


def test_demo_scenario_loads_28_employees(db):
    result = load_demo_data(db)
    assert result["employees_added"] == 28
    employees = crud.get_employees(db)
    assert len(employees) == 28


def test_demo_employees_have_required_fields(db):
    load_demo_data(db)
    for e in crud.get_employees(db):
        assert e.name
        assert e.role
        assert e.max_weekly_hours > 0


def test_demo_reload_is_idempotent_and_keeps_user_employees(db):
    load_demo_data(db)
    crud.create_employee(
        db,
        schemas.EmployeeIn(name="Manager Custom", role="Supervisor", max_weekly_hours=40),
    )
    result = load_demo_data(db)
    assert result["employees_added"] == 0
    employees = crud.get_employees(db)
    assert len(employees) == 29
    assert any(e.name == "Manager Custom" for e in employees)
    assert any(e.name == "Rahul" for e in employees)


def test_benchmark_adapter_converts_sample_instance():
    employees, shifts = load_benchmark_instance("sample_small_7day.json")
    assert len(employees) == 3
    assert len(shifts) == 9


def test_benchmark_data_reaches_optimizer_and_passes_validator():
    employees, shifts = load_benchmark_instance("sample_small_7day.json")
    assignment = generate_schedule(employees, shifts)
    assert set(assignment.keys()) == {s.id for s in shifts}
    violations = validate_schedule(employees, shifts, assignment)
    assert violations == []


def test_demo_data_generates_valid_schedule(db):
    load_demo_data(db)
    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    assignment = generate_schedule(sched_employees, sched_shifts)
    violations = validate_schedule(sched_employees, sched_shifts, assignment)
    assert violations == []


def test_demo_shifts_are_fully_covered(db):
    load_demo_data(db)
    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    assignment = generate_schedule(sched_employees, sched_shifts)
    assert len(sched_shifts) == 14
    for s in sched_shifts:
        assert len(assignment[s.id]) == s.required_staff
    assert validate_schedule(sched_employees, sched_shifts, assignment) == []
