"""ShiftGenie's internal scheduling representation.

Both the live database (via `from_db`) and the benchmark adapter convert
into these plain dataclasses before calling the optimizer, so the optimizer
never needs to know where the data came from.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

WEEK_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class SchedEmployee:
    id: str
    name: str
    role: str
    max_weekly_hours: float
    skills: List[str] = field(default_factory=list)
    verified_certifications: List[str] = field(default_factory=list)
    availability: List[Tuple[str, str, str]] = field(default_factory=list)  # (day, start, end)


@dataclass
class SchedShift:
    id: str
    day_of_week: str
    start_time: str
    end_time: str
    required_staff: int = 1
    required_roles: List[str] = field(default_factory=list)
    required_certifications: List[str] = field(default_factory=list)
    min_rest_hours: float = 0  # minimum rest required before/after this shift
    name: str = ""


def shift_label(shift: "SchedShift") -> str:
    """Human-readable shift label used in every user-facing message."""
    if shift.name:
        return f"{shift.name} ({shift.start_time}–{shift.end_time})"
    return f"{shift.day_of_week} {shift.start_time}–{shift.end_time}"


def _minutes(t: str) -> int:
    h, m = (int(x) for x in t.split(":"))
    return h * 60 + m


def shift_hours(shift: SchedShift) -> float:
    return (_minutes(shift.end_time) - _minutes(shift.start_time)) / 60


def rest_hours_between(shift_a: SchedShift, shift_b: SchedShift) -> Optional[float]:
    """Hours of rest if shift_b's day immediately follows shift_a's day; else None."""
    if shift_a.day_of_week not in WEEK_ORDER or shift_b.day_of_week not in WEEK_ORDER:
        return None
    ia, ib = WEEK_ORDER.index(shift_a.day_of_week), WEEK_ORDER.index(shift_b.day_of_week)
    if (ib - ia) % 7 != 1:
        return None
    return ((24 * 60 - _minutes(shift_a.end_time)) + _minutes(shift_b.start_time)) / 60


def from_db(employees, shifts) -> Tuple[List[SchedEmployee], List[SchedShift]]:
    """Convert EmployeeOut/ShiftOut (backend.schemas) objects into internal types."""
    sched_employees = [
        SchedEmployee(
            id=str(e.id),
            name=e.name,
            role=e.role,
            max_weekly_hours=e.max_weekly_hours,
            skills=[s.name for s in e.skills],
            verified_certifications=[
                c.name for c in e.certifications if c.verification_status == "verified"
            ],
            availability=[(a.day_of_week, a.start_time, a.end_time) for a in e.availabilities],
        )
        for e in employees
    ]
    sched_shifts = [
        SchedShift(
            id=str(s.id),
            day_of_week=s.day_of_week,
            start_time=s.start_time,
            end_time=s.end_time,
            required_staff=s.required_staff,
            required_roles=s.required_roles,
            required_certifications=s.required_certifications,
            name=getattr(s, "name", "") or "",
        )
        for s in shifts
    ]
    return sched_employees, sched_shifts
