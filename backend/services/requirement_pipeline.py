"""Maps a Gemini-parsed natural-language requirement into ShiftGenie's
internal scheduling types, then runs the existing OR-Tools/greedy scheduler
and deterministic validator. Gemini never assigns employees or validates —
it only produces the ParsedRequirement that this module turns into shifts.
"""

from dataclasses import replace
from typing import Iterable, List, Optional, Tuple

from backend.schemas import ParsedRequirement
from backend.services.scheduler import _is_eligible, solve_schedule
from backend.services.scheduler_types import WEEK_ORDER, SchedEmployee, SchedShift

# Generic words that describe "anyone"/"any credential" and must never become literal filters.
GENERIC_ROLE_TERMS = {
    "employee", "staff", "worker", "person", "people", "associate", "personnel",
    "anyone", "team member", "member", "colleague", "available",
}
GENERIC_CERT_TERMS = {
    "certification", "certificate", "certified", "qualified", "qualification",
    "license", "licence", "training", "credential", "required",
}


FILLER_WORDS = {"and", "or", "the", "valid", "proper", "relevant", "necessary", "needed", "any", "all", "verified", "with"}


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def _clean_terms(values: Iterable[str], generic: set, known: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Drop generic terms; map the rest onto known workforce names (case/plural-insensitive)."""
    canon = {k.lower(): k for k in known}
    kept, ignored = [], []
    for v in values:
        key = " ".join(v.strip().lower().split())
        words = key.split()
        is_known = key in canon or _singular(key) in canon
        if not key or (not is_known and (key in generic or _singular(key) in generic or all(
            w in FILLER_WORDS or _singular(w) in generic for w in words
        ))):
            ignored.append(v)
            continue
        kept.append(canon.get(key) or canon.get(_singular(key)) or v)
    return kept, ignored


def has_explicit_schedule(req: ParsedRequirement) -> bool:
    return bool(req.days or req.shift_start_time or req.shift_end_time)


def map_requirement_to_shifts(req: ParsedRequirement) -> List[SchedShift]:
    days = req.days or WEEK_ORDER
    start = req.shift_start_time or "09:00"
    end = req.shift_end_time or "17:00"
    staff = req.staffing_count or 1
    return [
        SchedShift(
            id=f"REQ-{day[:3]}",
            day_of_week=day,
            start_time=start,
            end_time=end,
            required_staff=staff,
            required_roles=req.roles,
            required_certifications=req.required_certifications,
            min_rest_hours=req.min_rest_hours or 0,
        )
        for day in days
    ]


def _cap_hours(employees: List[SchedEmployee], max_hours: int) -> List[SchedEmployee]:
    return [
        replace(e, max_weekly_hours=min(e.max_weekly_hours, max_hours)) for e in employees
    ]


def generate_schedule_from_requirement(
    req: ParsedRequirement,
    employees: List[SchedEmployee],
    existing_shifts: Optional[List[SchedShift]] = None,
    known_certifications: Optional[Iterable[str]] = None,
) -> dict:
    known_roles = {e.role for e in employees}
    known_certs = {c for e in employees for c in e.verified_certifications} | set(known_certifications or [])
    roles, ignored_roles = _clean_terms(req.roles, GENERIC_ROLE_TERMS, known_roles)
    certs, ignored_certs = _clean_terms(req.required_certifications, GENERIC_CERT_TERMS, known_certs)
    req = req.model_copy(update={"roles": roles, "required_certifications": certs})

    if req.max_hours:
        employees = _cap_hours(employees, req.max_hours)

    if not has_explicit_schedule(req) and existing_shifts:
        mode = "existing_shifts"
        shifts = [
            replace(
                s,
                required_staff=req.staffing_count or s.required_staff,
                required_roles=(
                    [r for r in s.required_roles if r.lower() in {x.lower() for x in roles}] or roles
                    if roles else s.required_roles
                ),
                required_certifications=sorted(set(s.required_certifications) | set(certs)),
                min_rest_hours=req.min_rest_hours or s.min_rest_hours,
            )
            for s in existing_shifts
        ]
    else:
        mode = "generated"
        shifts = map_requirement_to_shifts(req)

    solved = solve_schedule(employees, shifts)
    assignment = solved.assignment
    violations = solved.violations

    required_total = sum(s.required_staff for s in shifts)
    assigned_total = sum(len(v) for v in assignment.values())
    understaffed = [s.id for s in shifts if len(assignment.get(s.id, [])) < s.required_staff]
    feasible = not understaffed and not violations

    workload = {}
    for shift_id, emp_ids in assignment.items():
        for emp_id in emp_ids:
            workload[emp_id] = workload.get(emp_id, 0) + 1

    shift_details = [
        {
            "id": s.id, "day": s.day_of_week, "start": s.start_time, "end": s.end_time,
            "required": s.required_staff, "assigned": len(assignment.get(s.id, [])),
            "eligible": sum(1 for e in employees if _is_eligible(e, s)),
        }
        for s in shifts
    ]

    return {
        "feasible": feasible,
        "solver": solved.solver,
        "fallback_reason": solved.fallback_reason,
        "validated": solved.valid,
        "mode": mode,
        "assignments": assignment,
        "violations": violations,
        "ignored_terms": ignored_roles + ignored_certs,
        "shift_details": shift_details,
        "metrics": {
            "shifts_generated": len(shifts),
            "shifts_evaluated": len(shifts),
            "required_staff_total": required_total,
            "assigned_staff_total": assigned_total,
            "coverage_ratio": (assigned_total / required_total) if required_total else 1.0,
            "understaffed_shifts": understaffed,
            "employee_workload": workload,
        },
    }
