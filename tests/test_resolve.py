from backend.services.scheduler_types import SchedEmployee, SchedShift
from backend.services.simulation import relevant_resolutions, resolve_simulation, run_simulation


def small_infeasible():
    employees = [
        SchedEmployee(id="1", name="Rahul", role="Supervisor", max_weekly_hours=40,
                       availability=[("Monday", "08:00", "16:00")])
    ]
    shifts = [SchedShift(id="s1", day_of_week="Monday", start_time="08:00", end_time="16:00", required_staff=1)]
    return employees, shifts


def test_infeasible_simulation_has_structured_conflict():
    employees, shifts = small_infeasible()
    result = run_simulation("rahul_callout", employees, shifts)
    assert result["after"]["feasible"] is False
    assert result["understaffed_shifts"] == ["s1"]


def test_relevant_resolutions_returned_for_understaffing():
    keys = relevant_resolutions(["s1"], [])
    assert set(keys) == {"increase_capacity", "add_temp_staff", "reduce_coverage"}


def test_relevant_resolutions_for_max_hours_violation():
    keys = relevant_resolutions([], ["Bob exceeds max weekly hours"])
    assert "increase_max_hours" in keys
    assert "increase_capacity" not in keys


def test_resolution_modifies_only_temporary_data():
    employees, shifts = small_infeasible()
    orig_employees, orig_shifts = list(employees), list(shifts)
    resolve_simulation("rahul_callout", "add_temp_staff", employees, shifts)
    assert employees == orig_employees
    assert shifts == orig_shifts


def test_resolution_runs_through_scheduler_and_validator():
    employees, shifts = small_infeasible()
    result = resolve_simulation("rahul_callout", "add_temp_staff", employees, shifts)
    assert "assignments" in result and "violations" in result


def test_successful_resolution_feasible_true():
    employees, shifts = small_infeasible()
    result = resolve_simulation("rahul_callout", "add_temp_staff", employees, shifts)
    assert result["feasible"] is True
    assert result["remaining_understaffed"] == []


def test_insufficient_resolution_feasible_false():
    employees, shifts = small_infeasible()
    # reducing coverage on a single-shift, single-required-staff instance to 0 makes it trivially feasible;
    # instead verify a resolution that can't help (increase_max_hours) leaves it infeasible (no eligible employee).
    result = resolve_simulation("rahul_callout", "increase_max_hours", employees, shifts)
    assert result["feasible"] is False
    assert result["remaining_understaffed"] == ["s1"]


def test_original_data_unchanged_after_resolve():
    employees, shifts = small_infeasible()
    snapshot_emp = employees[0]
    resolve_simulation("rahul_callout", "increase_capacity", employees, shifts)
    assert employees[0] is snapshot_emp
    assert employees[0].availability == [("Monday", "08:00", "16:00")]


def test_existing_scenarios_still_work():
    employees, shifts = small_infeasible()
    result = run_simulation("rahul_callout", employees, shifts)
    assert result["available"] is True
