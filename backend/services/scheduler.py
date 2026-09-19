"""Shared scheduling optimizer. One interface used by the live data path, the
requirement pipeline, the what-if simulator and the benchmark adapter.

Flow (every path):  shared constraints -> OR-Tools -> validator -> valid schedule
                    OR-Tools fails/rejected -> Greedy fallback -> validator -> valid schedule
                    neither passes the validator -> safe failure (empty schedule, valid=False)

Both solvers read their rules from backend.services.constraints, and the independent
validator has the final word: an invalid schedule is never returned as valid.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.services import constraints as C
from backend.services.constraints import DEFAULT_CONSTRAINTS, HardConstraints
from backend.services.scheduler_types import SchedEmployee, SchedShift, shift_hours
from backend.services.validator import validate_report

Assignment = Dict[str, List[str]]


def _is_eligible(employee: SchedEmployee, shift: SchedShift, constraints: HardConstraints = DEFAULT_CONSTRAINTS) -> bool:
    return C.eligible(employee, shift, constraints)


@dataclass
class SolveResult:
    assignment: Assignment
    solver: str                      # "OR-Tools", "Greedy fallback" or "None"
    valid: bool                      # passed the independent validator (no hard violations)
    fully_covered: bool              # every shift has its required staff
    violations: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    gaps: List[dict] = field(default_factory=list)


def solve_schedule(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
    prefer: Optional[Assignment] = None,
) -> SolveResult:
    """Solve, validate, and only return schedules that pass the independent validator.
    `prefer` (an earlier assignment) makes the solvers keep existing assignments where possible."""
    attempts: List[str] = []
    for name, solver in (("OR-Tools", _solve_with_ortools), ("Greedy fallback", _solve_greedy)):
        try:
            assignment = solver(employees, shifts, constraints, prefer)
        except Exception as exc:
            attempts.append(f"{name} failed ({exc})")
            continue
        report = validate_report(employees, shifts, assignment, constraints)
        if not report.valid:
            attempts.append(f"{name} result rejected by validator ({len(report.hard)} violation(s))")
            continue
        return SolveResult(
            assignment=assignment, solver=name, valid=True, fully_covered=report.covered,
            violations=[], fallback_reason="; ".join(attempts) or None, gaps=report.gaps,
        )
    return SolveResult(
        assignment={s.id: [] for s in shifts}, solver="None", valid=False, fully_covered=False,
        violations=["No valid schedule found: " + "; ".join(attempts)], fallback_reason="; ".join(attempts),
        gaps=[{"shift_id": s.id, "required": s.required_staff, "assigned": 0} for s in shifts],
    )


def generate_schedule(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
    prefer: Optional[Assignment] = None,
) -> Assignment:
    """Return {shift_id: [employee_id, ...]} (validated). Kept for existing callers."""
    return solve_schedule(employees, shifts, constraints, prefer).assignment


def _solve_with_ortools(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
    prefer: Optional[Assignment] = None,
) -> Assignment:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    x = {
        (e.id, s.id): model.NewBoolVar(f"x_{e.id}_{s.id}")
        for e in employees
        for s in shifts
        if C.eligible(e, s, constraints)
    }

    # Never more staff than required.
    for s in shifts:
        vars_for_shift = [x[(e.id, s.id)] for e in employees if (e.id, s.id) in x]
        if vars_for_shift:
            model.Add(sum(vars_for_shift) <= s.required_staff)

    for e in employees:
        mine = [s for s in shifts if (e.id, s.id) in x]
        if constraints.enforce_weekly_hours and mine:
            model.Add(
                sum(int(shift_hours(s) * 60) * x[(e.id, s.id)] for s in mine) <= int(e.max_weekly_hours * 60)
            )
        for day in {s.day_of_week for s in mine}:
            same_day = [x[(e.id, s.id)] for s in mine if s.day_of_week == day]
            model.Add(sum(same_day) <= constraints.max_shifts_per_day)
        for i, a in enumerate(mine):
            for b in mine[i + 1:]:
                if C.pair_conflict(a, b, constraints):
                    model.Add(x[(e.id, a.id)] + x[(e.id, b.id)] <= 1)

    if x:
        keep = {(eid, sid) for sid, eids in (prefer or {}).items() for eid in eids}
        weight = len(x) + 1  # coverage always outweighs "keep the old assignment"
        model.Maximize(weight * sum(x.values()) + sum(v for k, v in x.items() if k in keep))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.random_seed = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"solver status {solver.StatusName(status)}")

    assignment: Assignment = {s.id: [] for s in shifts}
    for (emp_id, shift_id), var in x.items():
        if solver.Value(var):
            assignment[shift_id].append(emp_id)
    return assignment


def _solve_greedy(
    employees: List[SchedEmployee],
    shifts: List[SchedShift],
    constraints: HardConstraints = DEFAULT_CONSTRAINTS,
    prefer: Optional[Assignment] = None,
) -> Assignment:
    """Constraint-respecting fallback: same eligibility, daily limit, overlap, rest and
    weekly-hour rules as OR-Tools. Fills the most constrained shifts first."""
    prefer = prefer or {}
    assignment: Assignment = {s.id: [] for s in shifts}
    hours_used = {e.id: 0.0 for e in employees}
    day_count = {e.id: defaultdict(int) for e in employees}
    assigned = {e.id: [] for e in employees}
    candidates = {s.id: [e for e in employees if C.eligible(e, s, constraints)] for s in shifts}

    for s in sorted(shifts, key=lambda sh: len(candidates[sh.id])):
        ranked = sorted(candidates[s.id], key=lambda e: (e.id not in prefer.get(s.id, []), hours_used[e.id], e.name))
        for e in ranked:
            if len(assignment[s.id]) >= s.required_staff:
                break
            if constraints.enforce_weekly_hours and hours_used[e.id] + shift_hours(s) > e.max_weekly_hours:
                continue
            if day_count[e.id][s.day_of_week] >= constraints.max_shifts_per_day:
                continue
            if any(C.pair_conflict(other, s, constraints) for other in assigned[e.id]):
                continue
            assignment[s.id].append(e.id)
            hours_used[e.id] += shift_hours(s)
            day_count[e.id][s.day_of_week] += 1
            assigned[e.id].append(s)
    return assignment
