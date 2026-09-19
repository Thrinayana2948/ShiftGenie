from backend.schemas import ParsedRequirement
from backend.services.requirement_pipeline import (
    generate_schedule_from_requirement,
    map_requirement_to_shifts,
)
from backend.services.scheduler_types import SchedEmployee


def make_employee(**overrides):
    base = dict(
        id="1",
        name="Alice",
        role="Cashier",
        max_weekly_hours=40,
        skills=["Cash Handling"],
        verified_certifications=["Food Safety"],
        availability=[("Monday", "08:00", "18:00"), ("Tuesday", "08:00", "18:00")],
    )
    base.update(overrides)
    return SchedEmployee(**base)


def test_mapping_respects_fields():
    req = ParsedRequirement(
        staffing_count=2,
        roles=["Cashier"],
        required_certifications=["Food Safety"],
        days=["Monday"],
        shift_start_time="09:00",
        shift_end_time="17:00",
    )
    shifts = map_requirement_to_shifts(req)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.day_of_week == "Monday" and s.required_staff == 2
    assert s.required_roles == ["Cashier"]
    assert s.required_certifications == ["Food Safety"]


def test_valid_requirement_generates_schedule():
    req = ParsedRequirement(staffing_count=1, roles=["Cashier"], days=["Monday"])
    result = generate_schedule_from_requirement(req, [make_employee()])
    assert result["feasible"]
    assert result["violations"] == []
    assert result["metrics"]["assigned_staff_total"] == 1


def test_required_role_respected():
    req = ParsedRequirement(staffing_count=1, roles=["Supervisor"], days=["Monday"])
    result = generate_schedule_from_requirement(req, [make_employee(role="Cashier")])
    assert not result["feasible"]
    assert result["metrics"]["assigned_staff_total"] == 0


def test_certification_requirement_respected():
    req = ParsedRequirement(
        staffing_count=1, required_certifications=["First Aid"], days=["Monday"]
    )
    result = generate_schedule_from_requirement(req, [make_employee(verified_certifications=[])])
    assert not result["feasible"]
    assert result["metrics"]["assigned_staff_total"] == 0


def test_availability_respected():
    req = ParsedRequirement(staffing_count=1, days=["Wednesday"])
    result = generate_schedule_from_requirement(req, [make_employee()])  # only Mon/Tue available
    assert not result["feasible"]


def test_max_hours_respected():
    req = ParsedRequirement(staffing_count=1, days=["Monday"], max_hours=2)
    emp = make_employee(availability=[("Monday", "08:00", "18:00")])
    result = generate_schedule_from_requirement(req, [emp])
    # shift default 09:00-17:00 = 8h > capped 2h max, so cannot be assigned
    assert not result["feasible"]
    assert result["metrics"]["assigned_staff_total"] == 0


def test_impossible_requirement_is_infeasible():
    req = ParsedRequirement(staffing_count=5, roles=["Supervisor"], days=["Monday"])
    result = generate_schedule_from_requirement(req, [make_employee(role="Cashier")])
    assert result["feasible"] is False
    assert result["metrics"]["understaffed_shifts"] == ["REQ-Mon"]
