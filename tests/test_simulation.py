from backend.services.scheduler_types import SchedEmployee, SchedShift
from backend.services.simulation import run_simulation


def make_employees():
    return [
        SchedEmployee(
            id="1", name="Rahul", role="Supervisor", max_weekly_hours=40,
            verified_certifications=[],
            availability=[("Monday", "08:00", "16:00"), ("Saturday", "08:00", "16:00")],
        ),
        SchedEmployee(
            id="2", name="Priya", role="Cashier", max_weekly_hours=40,
            verified_certifications=[],
            availability=[("Monday", "08:00", "16:00"), ("Saturday", "08:00", "16:00")],
        ),
        SchedEmployee(
            id="3", name="Karan", role="Cashier", max_weekly_hours=40,
            verified_certifications=[],
            availability=[("Monday", "08:00", "16:00"), ("Saturday", "08:00", "16:00")],
        ),
    ]


def make_shifts():
    return [
        SchedShift(id="s1", day_of_week="Monday", start_time="08:00", end_time="16:00", required_staff=1),
        SchedShift(id="s2", day_of_week="Saturday", start_time="08:00", end_time="16:00", required_staff=1),
    ]


def test_rahul_callout_only_changes_availability():
    employees, shifts = make_employees(), make_shifts()
    result = run_simulation("rahul_callout", employees, shifts)
    assert result["available"] is True
    # original objects untouched
    assert employees[0].availability != []


def test_priya_callout_only_changes_availability():
    result = run_simulation("priya_callout", make_employees(), make_shifts())
    assert result["available"] is True


def test_weekend_demand_increases_requirement():
    result = run_simulation("weekend_demand", make_employees(), make_shifts())
    assert result["after"]["required_staff_total"] > result["before"]["required_staff_total"]


def test_supervisor_unavailable_handled():
    result = run_simulation("supervisor_unavailable", make_employees(), make_shifts())
    assert result["available"] is True
    assert "Supervisor" in result["note"]


def test_reduce_capacity_handled():
    result = run_simulation("reduce_capacity", make_employees(), make_shifts())
    assert result["available"] is True


def test_original_data_unchanged():
    employees, shifts = make_employees(), make_shifts()
    orig_emp_copy = list(employees)
    orig_shift_copy = list(shifts)
    run_simulation("weekend_demand", employees, shifts)
    assert employees == orig_emp_copy
    assert shifts == orig_shift_copy


def test_original_schedule_unchanged_across_scenarios():
    employees, shifts = make_employees(), make_shifts()
    r1 = run_simulation("rahul_callout", employees, shifts)
    r2 = run_simulation("priya_callout", employees, shifts)
    assert r1["before"] == r2["before"]


def test_feasible_simulation_returns_valid_schedule():
    result = run_simulation("weekend_demand", make_employees(), make_shifts())
    assert result["after"]["feasible"] is True
    assert result["after_violations"] == []


def test_infeasible_simulation_returns_structured_conflict():
    small = [
        SchedEmployee(id="1", name="Rahul", role="Supervisor", max_weekly_hours=40,
                       availability=[("Monday", "08:00", "16:00")])
    ]
    shifts = [SchedShift(id="s1", day_of_week="Monday", start_time="08:00", end_time="16:00", required_staff=1)]
    result = run_simulation("rahul_callout", small, shifts)
    assert result["available"] is True
    assert result["after"]["feasible"] is False
    assert result["understaffed_shifts"] == ["s1"]
    assert len(result["resolution_options"]) > 0


def test_missing_employee_scenario_is_unavailable_not_crash():
    employees = [e for e in make_employees() if e.name != "Rahul"]
    result = run_simulation("rahul_callout", employees, make_shifts())
    assert result["available"] is False
    assert "message" in result
