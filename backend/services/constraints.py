"""Single source of truth for ShiftGenie's hard scheduling constraints.

The OR-Tools model, the greedy fallback and the independent validator all import
these rules and values, so a constraint is defined exactly once:

    HardConstraints (values) + predicates below  ->  OR-Tools / Greedy / Validator
"""

from dataclasses import dataclass

from backend.services.scheduler_types import (
    SchedEmployee,
    SchedShift,
    _minutes,
    rest_hours_between,
)


@dataclass(frozen=True)
class HardConstraints:
    max_shifts_per_day: int = 1          # one shift per employee per day
    forbid_overlap: bool = True          # overlapping shifts are never allowed
    enforce_availability: bool = True
    enforce_role: bool = True
    enforce_certifications: bool = True  # only *verified* certifications count
    enforce_weekly_hours: bool = True    # employee.max_weekly_hours is a hard cap
    enforce_rest: bool = True            # shift.min_rest_hours between consecutive days


DEFAULT_CONSTRAINTS = HardConstraints()


def role_ok(e: SchedEmployee, s: SchedShift) -> bool:
    return not s.required_roles or e.role.lower() in {r.lower() for r in s.required_roles}


def certs_ok(e: SchedEmployee, s: SchedShift) -> bool:
    have = {c.lower() for c in e.verified_certifications}
    return all(c.lower() in have for c in s.required_certifications)


def is_available(e: SchedEmployee, s: SchedShift) -> bool:
    return any(
        day == s.day_of_week and start <= s.start_time and end >= s.end_time
        for day, start, end in e.availability
    )


def eligible(e: SchedEmployee, s: SchedShift, c: HardConstraints = DEFAULT_CONSTRAINTS) -> bool:
    """Per-shift eligibility: role, verified certification and availability."""
    if c.enforce_role and not role_ok(e, s):
        return False
    if c.enforce_certifications and not certs_ok(e, s):
        return False
    if c.enforce_availability and not is_available(e, s):
        return False
    return True


def overlaps(a: SchedShift, b: SchedShift) -> bool:
    return (
        a.day_of_week == b.day_of_week
        and max(_minutes(a.start_time), _minutes(b.start_time)) < min(_minutes(a.end_time), _minutes(b.end_time))
    )


def rest_conflict(a: SchedShift, b: SchedShift, c: HardConstraints = DEFAULT_CONSTRAINTS) -> bool:
    if not c.enforce_rest:
        return False
    need = max(a.min_rest_hours, b.min_rest_hours)
    if need <= 0:
        return False
    return any(g is not None and g < need for g in (rest_hours_between(a, b), rest_hours_between(b, a)))


def pair_conflict(a: SchedShift, b: SchedShift, c: HardConstraints = DEFAULT_CONSTRAINTS) -> bool:
    """True if one employee may not work both shifts (overlap or insufficient rest)."""
    if a.id == b.id:
        return False
    return (c.forbid_overlap and overlaps(a, b)) or rest_conflict(a, b, c)
