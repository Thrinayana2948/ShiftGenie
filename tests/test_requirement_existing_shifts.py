from backend.schemas import ParsedRequirement
from backend.services.requirement_pipeline import generate_schedule_from_requirement
from backend.services.scheduler_types import SchedEmployee, SchedShift


def employees():
    return [
        SchedEmployee(id="1", name="Ana", role="Cashier", max_weekly_hours=40,
                      verified_certifications=["Food Safety"],
                      availability=[("Monday", "08:00", "16:00"), ("Tuesday", "12:00", "20:00")]),
        SchedEmployee(id="2", name="Ben", role="Supervisor", max_weekly_hours=40,
                      availability=[("Monday", "08:00", "16:00")]),
    ]


def demo_shifts():
    return [
        SchedShift(id="10", day_of_week="Monday", start_time="08:00", end_time="16:00", required_staff=2),
        SchedShift(id="11", day_of_week="Tuesday", start_time="12:00", end_time="20:00", required_staff=1),
    ]


def test_generic_requirement_uses_existing_shifts():
    req = ParsedRequirement(staffing_count=1)
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert r["mode"] == "existing_shifts"
    assert set(r["assignments"]) == {"10", "11"}
    assert all(d["start"] in ("08:00", "12:00") for d in r["shift_details"])  # no fabricated 09:00-17:00
    assert r["metrics"]["required_staff_total"] == 2  # 1 per shift
    assert r["feasible"] is True


def test_no_staffing_count_keeps_shift_requirements():
    r = generate_schedule_from_requirement(ParsedRequirement(), employees(), demo_shifts())
    assert r["metrics"]["required_staff_total"] == 3


def test_generic_employee_is_not_a_role_filter():
    req = ParsedRequirement(staffing_count=1, roles=["employee"])
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert "employee" in r["ignored_terms"]
    assert r["feasible"] is True


def test_generic_certifications_is_not_a_cert_filter():
    req = ParsedRequirement(staffing_count=1, required_certifications=["certifications", "Certified"])
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert set(r["ignored_terms"]) == {"certifications", "Certified"}
    assert r["feasible"] is True


def test_real_certification_still_enforced():
    req = ParsedRequirement(staffing_count=1, required_certifications=["food safety"])
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    # only Ana is verified; Monday 08-16 has Ana eligible, Tuesday too -> feasible, and Ben never assigned
    assert "2" not in [e for v in r["assignments"].values() for e in v]


def test_unknown_certification_remains_hard_constraint():
    req = ParsedRequirement(staffing_count=1, required_certifications=["Forklift License X"])
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert r["feasible"] is False
    assert all(d["eligible"] == 0 for d in r["shift_details"])


def test_explicit_day_time_role_preserved():
    req = ParsedRequirement(staffing_count=1, roles=["cashier"], days=["Monday"],
                            shift_start_time="08:00", shift_end_time="16:00")
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert r["mode"] == "generated"
    assert list(r["assignments"]) == ["REQ-Mon"]
    assert r["assignments"]["REQ-Mon"] == ["1"]  # cashier role enforced (Ben is Supervisor)
    assert r["feasible"] is True


def test_max_hours_and_rest_still_apply_to_existing_shifts():
    req = ParsedRequirement(staffing_count=1, max_hours=4)
    r = generate_schedule_from_requirement(req, employees(), demo_shifts())
    assert r["metrics"]["assigned_staff_total"] == 0  # 8h shifts exceed 4h cap
    assert r["feasible"] is False


def test_no_existing_shifts_falls_back_to_generated():
    r = generate_schedule_from_requirement(ParsedRequirement(staffing_count=1), employees(), [])
    assert r["mode"] == "generated"
