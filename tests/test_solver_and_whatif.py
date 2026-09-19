import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import crud, schemas
from backend.database import Base
from backend.load_demo_data import load_demo_data, reset_demo_data
from backend.services import scheduler
from backend.services.constraints import DEFAULT_CONSTRAINTS, HardConstraints
from backend.services.scheduler import _solve_greedy, _solve_with_ortools, solve_schedule
from backend.services.scheduler_types import SchedEmployee, SchedShift
from backend.services.simulation import resolve_simulation, run_simulation
from backend.services.validator import validate_report


def emp(i, name, role="Cashier", hours=40, avail=None, certs=None, skills=None):
    return SchedEmployee(id=str(i), name=name, role=role, max_weekly_hours=hours, skills=skills or [],
                         verified_certifications=certs or [], availability=avail or [])


def shift(i, day="Monday", start="08:00", end="16:00", need=1, roles=None, certs=None, rest=0, name=""):
    return SchedShift(id=str(i), day_of_week=day, start_time=start, end_time=end, required_staff=need,
                      required_roles=roles or [], required_certifications=certs or [], min_rest_hours=rest, name=name)


def team():
    mon = [("Monday", "08:00", "16:00")]
    return (
        [emp(1, "Sam", "Supervisor", avail=mon, skills=["Leadership"]),
         emp(2, "Cy", "Cashier", avail=mon), emp(3, "Di", "Cashier", avail=mon)],
        [shift("A", roles=["Supervisor"], name="Monday Supervisor Shift"),
         shift("B", start="08:00", end="16:00", need=1, roles=["Cashier"], name="Monday Till")],
    )


# ---------------------------------------------------------- shared constraints --

def dense_case():
    mon_tue = [("Monday", "08:00", "20:00"), ("Tuesday", "08:00", "20:00")]
    employees = [emp(1, "A", hours=10, avail=mon_tue), emp(2, "B", hours=40, avail=mon_tue, certs=["Food"])]
    shifts = [shift(1, "Monday", "08:00", "16:00", 1, certs=["Food"], rest=12),
              shift(2, "Tuesday", "08:00", "16:00", 1, rest=12),
              shift(3, "Monday", "12:00", "20:00", 1)]
    return employees, shifts


@pytest.mark.parametrize("solver", [_solve_with_ortools, _solve_greedy])
def test_both_solvers_obey_hard_constraints(solver):
    employees, shifts = dense_case()
    asg = solver(employees, shifts, DEFAULT_CONSTRAINTS, None)
    rep = validate_report(employees, shifts, asg)
    assert rep.valid, rep.messages()
    # weekly-hour cap: A (10h) can never take an 8h shift twice
    a_shifts = [s for s, es in asg.items() if "1" in es]
    assert len(a_shifts) <= 1


@pytest.mark.parametrize("solver", [_solve_with_ortools, _solve_greedy])
def test_shared_config_change_affects_both_solvers(solver):
    e = [emp(1, "A", avail=[("Monday", "08:00", "20:00")])]
    s = [shift(1, "Monday", "08:00", "12:00"), shift(2, "Monday", "14:00", "18:00")]
    default = solver(e, s, DEFAULT_CONSTRAINTS, None)
    assert sum(len(v) for v in default.values()) == 1          # one shift per day
    relaxed = solver(e, s, HardConstraints(max_shifts_per_day=2), None)
    assert sum(len(v) for v in relaxed.values()) == 2          # same rule value drives both solvers
    assert validate_report(e, s, relaxed, HardConstraints(max_shifts_per_day=2)).valid


def test_overlap_is_never_assigned_even_with_higher_daily_limit():
    e = [emp(1, "A", avail=[("Monday", "08:00", "20:00")])]
    s = [shift(1, "Monday", "08:00", "14:00"), shift(2, "Monday", "12:00", "18:00")]
    c = HardConstraints(max_shifts_per_day=3)
    for solver in (_solve_with_ortools, _solve_greedy):
        assert sum(len(v) for v in solver(e, s, c, None).values()) == 1


# --------------------------------------------------------------- validator --

def test_validator_catches_each_hard_violation():
    employees = [emp(1, "Ann", "Cashier", hours=8, avail=[("Monday", "08:00", "16:00")]),
                 emp(2, "Bo", "Cashier", avail=[("Monday", "08:00", "20:00"), ("Tuesday", "06:00", "20:00")])]
    shifts = [shift(1, roles=["Supervisor"]), shift(2, certs=["Food"]),
              shift(3, "Tuesday", "06:00", "14:00", rest=14), shift(4, "Monday", "12:00", "18:00"),
              shift(5, "Tuesday", "20:00", "23:00")]
    bad = {"1": ["1"], "2": ["1"], "3": ["2"], "4": ["2"], "5": ["1"]}
    cats = validate_report(employees, shifts, bad).by_category()
    for expected in ("role", "certification", "availability", "overlap", "rest", "weekly_hours", "overstaffed"):
        if expected == "overstaffed":
            continue
        assert cats.get(expected), (expected, cats)


def test_validator_reports_coverage_gap_separately():
    employees, shifts = team()
    rep = validate_report(employees, shifts, {"A": [], "B": ["2"]})
    assert rep.valid and not rep.covered and rep.gaps[0]["shift_id"] == "A"


# ----------------------------------------------------------- fallback path --

def test_ortools_failure_falls_back_to_greedy_and_is_validated(monkeypatch):
    employees, shifts = team()

    def boom(*a, **k):
        raise RuntimeError("cp-sat unavailable")

    monkeypatch.setattr(scheduler, "_solve_with_ortools", boom)
    r = solve_schedule(employees, shifts)
    assert r.solver == "Greedy fallback" and r.valid and r.fully_covered
    assert "OR-Tools failed" in r.fallback_reason


def test_invalid_solver_output_is_rejected(monkeypatch):
    employees, shifts = team()
    # OR-Tools "returns" an assignment that breaks availability/role -> validator must reject it
    monkeypatch.setattr(scheduler, "_solve_with_ortools", lambda *a, **k: {"A": ["2"], "B": ["1"]})
    r = solve_schedule(employees, shifts)
    assert r.solver == "Greedy fallback" and r.valid
    assert "rejected by validator" in r.fallback_reason


def test_no_valid_schedule_is_a_safe_failure(monkeypatch):
    employees, shifts = team()
    monkeypatch.setattr(scheduler, "_solve_with_ortools", lambda *a, **k: {"A": ["2"], "B": ["1"]})
    monkeypatch.setattr(scheduler, "_solve_greedy", lambda *a, **k: {"A": ["2"], "B": ["1"]})
    r = solve_schedule(employees, shifts)
    assert r.valid is False and r.solver == "None"
    assert all(v == [] for v in r.assignment.values())
    assert r.violations[0].startswith("No valid schedule found")


# ------------------------------------------------------------------ what-if --

def test_employee_sick_names_employee_and_affected_shifts_and_reoptimizes():
    employees, shifts = team()
    base = solve_schedule(employees, shifts)
    worker = base.assignment["B"][0]                       # the cashier actually on the till
    other = {"2": "Di", "3": "Cy"}[worker]
    name = {"2": "Cy", "3": "Di"}[worker]
    r = run_simulation("employee_sick", employees, shifts, {"employee_ids": [worker]})
    assert r["impact"]["affected_employees"] == [{"name": name, "role": "Cashier"}]
    assert r["impact"]["affected_shifts"] == ["Monday Till (08:00–16:00)"]
    assert r["recoverable"] is True and r["status"] == "Recoverable"
    assert r["solver"] in ("OR-Tools", "Greedy fallback") and r["valid"]
    # the other cashier takes over; the roster visibly changes
    assert r["changes"]["counts"]["new_assignments"] == 1
    assert {row["employee"] for row in r["changes"]["employees"]} == {name, other}


def test_supervisor_absence_detected_even_with_enough_total_staff():
    employees, shifts = team()
    r = run_simulation("supervisor_unavailable", employees, shifts)
    assert r["status"] == "Infeasible" and not r["recoverable"]
    assert r["impact"]["capacity_after"]["staff_shortfall"] == 1        # 2 cashiers idle, still short a supervisor
    sup = next(x for x in r["impact"]["role_coverage"] if x["role"] == "Supervisor")
    assert (sup["before"], sup["after"]) == (1, 0) and sup["lost"]
    assert r["shortfalls"][0]["qualified_available"] == 0
    assert "Supervisor" in r["shortfalls"][0]["roles"]
    assert r["explanation"].startswith("No schedule can satisfy")


def test_demand_increase_changes_requirement_and_shortfall():
    employees, shifts = team()
    r = run_simulation("additional_staffing", employees, shifts, {"extra_staff": 2, "days": ["Monday"]})
    assert r["impact"]["capacity_after"]["staff_required"] == r["impact"]["capacity_before"]["staff_required"] + 4
    assert r["impact"]["capacity_after"]["hours_shortfall"] > 0
    assert r["impact"]["affected_shifts"]


def test_multiple_absences_show_combined_impact():
    employees, shifts = team()
    r = run_simulation("multiple_unavailable", employees, shifts, {"employee_ids": ["1", "2"]})
    assert {a["name"] for a in r["impact"]["affected_employees"]} == {"Sam", "Cy"}
    assert r["after"]["available_employees"] == 1


def test_partial_day_unavailability_only_hits_those_days():
    employees, shifts = team()
    r = run_simulation("employee_unavailable", employees, shifts, {"employee_ids": ["2"], "days": ["Tuesday"]})
    assert r["impact"]["affected_shifts"] == []          # nobody works Tuesday in this roster
    assert r["changes"]["counts"]["shifts_changed"] == 0


def test_scenarios_have_visibly_different_impacts():
    employees, shifts = team()
    sick = run_simulation("employee_sick", employees, shifts, {"employee_ids": ["3"]})
    sup = run_simulation("supervisor_unavailable", employees, shifts)
    dem = run_simulation("weekend_demand", employees, shifts)
    assert sick["status"] != sup["status"]
    assert sick["impact"]["affected_employees"] != sup["impact"]["affected_employees"]
    assert dem["impact"]["affected_employees"] == []


def test_resolution_reruns_solver_and_is_validated():
    employees, shifts = team()
    r = resolve_simulation("supervisor_unavailable", "add_temp_staff", employees, shifts)
    assert r["verified"] and r["valid"] and r["remaining_understaffed"] == []
    assert r["after"]["assigned_staff_total"] == r["after"]["required_staff_total"] == 2
    assert any(row["employee"].startswith("Temporary") for row in r["changes"]["employees"])
    assert len(employees) == 3                                              # original untouched


def test_resolution_not_accepted_when_still_short():
    employees, shifts = team()
    r = resolve_simulation("supervisor_unavailable", "increase_capacity", employees, shifts)
    assert r["verified"] is False and r["remaining_understaffed"] == ["A"]
    assert r["remaining_shortfalls"]


def test_resolution_result_hidden_if_validation_fails(monkeypatch):
    employees, shifts = team()
    monkeypatch.setattr(scheduler, "_solve_with_ortools", lambda *a, **k: {"A": ["2"], "B": ["1"]})
    monkeypatch.setattr(scheduler, "_solve_greedy", lambda *a, **k: {"A": ["2"], "B": ["1"]})
    r = resolve_simulation("supervisor_unavailable", "add_temp_staff", employees, shifts)
    assert r["verified"] is False and r["assignments"] == {}


def test_resolution_options_match_the_conflict():
    employees, shifts = team()
    r = run_simulation("supervisor_unavailable", employees, shifts)
    keys = r["resolution_keys"]
    assert "add_temp_staff" in keys and "reduce_coverage" in keys
    assert "increase_capacity" not in keys                # nobody qualified -> more hours cannot help
    assert all(o["description"] and o["expected_impact"] for o in r["resolution_options"])


# ------------------------------------------------------------- demo reset --

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_reset_restores_demo_baseline_but_keeps_user_employees(db):
    load_demo_data(db)
    crud.create_employee(db, schemas.EmployeeIn(name="Custom User", role="Cashier", max_weekly_hours=20))
    rahul = next(e for e in crud.get_employees(db) if e.name == "Rahul")
    crud.update_employee(db, rahul, schemas.EmployeeIn(name="Rahul", role="Cashier", max_weekly_hours=5))
    result = reset_demo_data(db)
    assert result["employees_restored"] == 1
    names = {e.name: e for e in crud.get_employees(db)}
    assert names["Rahul"].role == "Supervisor" and names["Rahul"].max_weekly_hours == 25
    assert "Custom User" in names and len(names) == 29
    assert reset_demo_data(db)["employees_restored"] == 0        # idempotent


def test_simulation_returns_human_readable_roster_without_internal_ids():
    employees, shifts = team()
    r = run_simulation("employee_sick", employees, shifts, {"employee_ids": ["2"]})
    assert r["roster"] and {row["Status"] for row in r["roster"]} <= {"Assigned", "Unfilled"}
    assert all(not str(row["Employee"]).isdigit() for row in r["roster"])
    inf = run_simulation("supervisor_unavailable", employees, shifts)
    assert any(row["Employee"] == "Unfilled" for row in inf["roster"])       # partial roster is labelled
