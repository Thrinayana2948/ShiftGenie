"""Independent validator. Re-derives every hard-constraint check from the raw
employees, shifts and assignment — it never trusts a solver's status. It uses the
same shared rules (backend.services.constraints) as OR-Tools and the greedy
fallback, so all three agree on what "valid" means.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from backend.services import constraints as C
from backend.services.constraints import DEFAULT_CONSTRAINTS, HardConstraints
from backend.services.scheduler_types import SchedEmployee, SchedShift, shift_hours, shift_label


@dataclass
class ValidationReport:
    hard: List[dict] = field(default_factory=list)   # hard-constraint violations
    gaps: List[dict] = field(default_factory=list)   # staffing shortfalls (coverage)

    @property
    def valid(self) -> bool:
        return not self.hard

    @property
    def covered(self) -> bool:
        return not self.gaps

    def messages(self) -> List[str]:
        return [v["message"] for v in self.hard]

    def by_category(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for v in self.hard:
            out[v["category"]] = out.get(v["category"], 0) + 1
        return out


def validate_report(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    assignment: Dict[str, List[str]],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
) -> ValidationReport:
    rep = ValidationReport()
    emp_by_id = {e.id: e for e in employees}
    shift_by_id = {s.id: s for s in shifts}
    worked: Dict[str, List[SchedShift]] = {}

    def add(category, message, shift_id=None, employee_id=None):
        rep.hard.append({"category": category, "message": message, "shift_id": shift_id, "employee_id": employee_id})

    for sid, eids in assignment.items():
        s = shift_by_id.get(sid)
        if s is None:
            add("data", f"Unknown shift id {sid}", sid)
            continue
        if len(set(eids)) != len(eids):
            add("data", f"{shift_label(s)} lists the same employee twice", sid)
        if len(eids) > s.required_staff:
            add("overstaffed", f"{shift_label(s)} is overstaffed: {len(eids)}/{s.required_staff}", sid)
        for eid in eids:
            e = emp_by_id.get(eid)
            if e is None:
                add("data", f"Unknown employee id {eid} on {shift_label(s)}", sid, eid)
                continue
            if constraints.enforce_role and not C.role_ok(e, s):
                add("role", f"{e.name} lacks required role for {shift_label(s)}", sid, eid)
            if constraints.enforce_certifications and not C.certs_ok(e, s):
                add("certification", f"{e.name} lacks verified certification for {shift_label(s)}", sid, eid)
            if constraints.enforce_availability and not C.is_available(e, s):
                add("availability", f"{e.name} not available for {shift_label(s)}", sid, eid)
            worked.setdefault(eid, []).append(s)

    for eid, ss in worked.items():
        e = emp_by_id.get(eid)
        if e is None:
            continue
        if constraints.enforce_weekly_hours and sum(shift_hours(s) for s in ss) > e.max_weekly_hours:
            add("weekly_hours", f"{e.name} exceeds max weekly hours", None, eid)
        by_day: Dict[str, List[SchedShift]] = {}
        for s in ss:
            by_day.setdefault(s.day_of_week, []).append(s)
        for day, day_shifts in by_day.items():
            if constraints.forbid_overlap and any(
                C.overlaps(a, b) for i, a in enumerate(day_shifts) for b in day_shifts[i + 1:]
            ):
                add("overlap", f"{e.name} has overlapping shifts on {day}", None, eid)
            elif len(day_shifts) > constraints.max_shifts_per_day:
                add("daily_limit", f"{e.name} is double-booked on {day}", None, eid)
        for i, a in enumerate(ss):
            for b in ss[i + 1:]:
                if C.rest_conflict(a, b, constraints):
                    add("rest", f"{e.name} has insufficient rest between shifts", None, eid)

    for s in shifts:
        got = len(assignment.get(s.id, []))
        if got < s.required_staff:
            rep.gaps.append({"shift_id": s.id, "required": s.required_staff, "assigned": got})
    return rep


def validate_schedule(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    assignment: Dict[str, List[str]],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
) -> List[str]:
    """Hard-constraint violation messages (empty list = valid). Coverage gaps are reported separately."""
    return validate_report(employees, shifts, assignment, constraints).messages()
