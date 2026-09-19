"""What-if simulation + resolution.

Every scenario modifies an in-memory copy of the workforce/requirements (the database
is never written), re-optimizes with the shared solver (OR-Tools -> Greedy fallback),
and passes the result through the independent validator (all inside `solve_schedule`).
The response is human-readable: scenario-specific impact, feasibility, a before/after
roster comparison, shortfalls and resolution options that are verified by re-solving.
"""

import math
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

from backend.services import constraints as C
from backend.services.scheduler import solve_schedule
from backend.services.scheduler_types import (
    WEEK_ORDER,
    SchedEmployee,
    SchedShift,
    shift_hours,
    shift_label,
)

WEEKEND = ("Saturday", "Sunday")
Params = Dict[str, object]


# ------------------------------------------------------------------ helpers --

def _find_employee(employees: List[SchedEmployee], name: str = None, role: str = None) -> Optional[SchedEmployee]:
    for e in employees:
        if name and e.name.lower() == name.lower():
            return e
        if role and e.role.lower() == role.lower():
            return e
    return None


def _worked_hours(shifts: List[SchedShift], assignment: dict) -> Dict[str, float]:
    by_id = {s.id: s for s in shifts}
    hours: Dict[str, float] = {}
    for sid, eids in assignment.items():
        for eid in eids:
            if sid in by_id:
                hours[eid] = hours.get(eid, 0.0) + shift_hours(by_id[sid])
    return hours


def _busiest(employees, shifts, assignment, n=1, role=None) -> List[SchedEmployee]:
    hours = _worked_hours(shifts, assignment)
    pool = [e for e in employees if role is None or e.role.lower() == role.lower()]
    return sorted(pool, key=lambda e: (-hours.get(e.id, 0.0), e.name))[:n]


def _ids(params: Params) -> List[str]:
    return [str(i) for i in (params.get("employee_ids") or [])]


def _remove_availability(employees, ids, days=None):
    ids = set(ids)
    out = []
    for e in employees:
        if e.id in ids:
            keep = [] if not days else [a for a in e.availability if a[0] not in days]
            e = replace(e, availability=keep)
        out.append(e)
    return out


# ---------------------------------------------------------------- scenarios --
# Each returns (employees, shifts, note, affected_employee_ids); employees=None => not applicable.

def _absent(employees, shifts, ids, note_fmt, days=None):
    people = [e for e in employees if e.id in set(ids)]
    if not people:
        return None, shifts, "The selected employee(s) were not found in the current workforce.", []
    names = ", ".join(e.name for e in people)
    return _remove_availability(employees, ids, days), shifts, note_fmt.format(names=names), [e.id for e in people]


def scenario_employee_sick(employees, shifts, params, baseline):
    ids = _ids(params) or [e.id for e in _busiest(employees, shifts, baseline, 1)]
    return _absent(employees, shifts, ids, "{names} calls in sick and is unavailable for the whole week (simulation only).")


def scenario_employee_unavailable(employees, shifts, params, baseline):
    ids = _ids(params) or [e.id for e in _busiest(employees, shifts, baseline, 1)]
    days = [str(d) for d in (params.get("days") or [])]
    when = f"on {', '.join(days)}" if days else "for the whole week"
    return _absent(employees, shifts, ids, "{names} becomes unavailable " + when + " (simulation only).", days or None)


def scenario_multiple_unavailable(employees, shifts, params, baseline):
    ids = _ids(params) or [e.id for e in _busiest(employees, shifts, baseline, 2)]
    return _absent(employees, shifts, ids, "{names} are all unavailable for the whole week (simulation only).")


def scenario_supervisor_unavailable(employees, shifts, params, baseline):
    ids = _ids(params)
    if not ids:
        sup = _busiest(employees, shifts, baseline, 1, role="Supervisor")
        ids = [e.id for e in sup]
    if not ids:
        return None, shifts, "No Supervisor found in the current workforce.", []
    return _absent(employees, shifts, ids, "Supervisor {names} is unavailable for the whole week (simulation only).")


def _named(name):
    def fn(employees, shifts, params, baseline):
        target = _find_employee(employees, name=name)
        if not target:
            return None, shifts, f"{name} was not found in the current workforce.", []
        return _absent(employees, shifts, [target.id], "{names} is marked unavailable for this simulation only.")
    return fn


def scenario_weekend_demand(employees, shifts, params, baseline):
    pct = float(params.get("percent") or 20)
    new_shifts = [
        replace(s, required_staff=math.ceil(s.required_staff * (1 + pct / 100)))
        if s.day_of_week in WEEKEND else s
        for s in shifts
    ]
    return employees, new_shifts, f"Weekend required staffing increased by {pct:.0f}%.", []


def scenario_additional_staffing(employees, shifts, params, baseline):
    extra = int(params.get("extra_staff") or 1)
    days = [str(d) for d in (params.get("days") or [])] or WEEK_ORDER
    new_shifts = [replace(s, required_staff=s.required_staff + extra) if s.day_of_week in days else s for s in shifts]
    return employees, new_shifts, f"+{extra} required staff on every shift on {', '.join(days) if days != WEEK_ORDER else 'all days'}.", []


def scenario_reduce_capacity(employees, shifts, params, baseline):
    pct = float(params.get("percent") or 40)
    new = [replace(e, max_weekly_hours=max(0, round(e.max_weekly_hours * (1 - pct / 100)))) for e in employees]
    return new, shifts, f"Every employee's weekly-hour limit reduced by {pct:.0f}% (capacity cut).", [e.id for e in employees]


SCENARIOS = {
    "employee_sick": ("Employee calls in sick", scenario_employee_sick),
    "employee_unavailable": ("Employee becomes unavailable", scenario_employee_unavailable),
    "multiple_unavailable": ("Multiple employees unavailable", scenario_multiple_unavailable),
    "supervisor_unavailable": ("Supervisor unavailable", scenario_supervisor_unavailable),
    "weekend_demand": ("Weekend demand increases", scenario_weekend_demand),
    "additional_staffing": ("Additional staffing requirement", scenario_additional_staffing),
    "reduce_capacity": ("Reduce staff capacity", scenario_reduce_capacity),
    "rahul_callout": ("Rahul Call-Out", _named("Rahul")),
    "priya_callout": ("Priya Call-Out", _named("Priya")),
}


# ------------------------------------------------------------------ metrics --

def _metrics(employees: List[SchedEmployee], shifts: List[SchedShift], solved) -> dict:
    assignment = solved.assignment
    required = sum(s.required_staff for s in shifts)
    assigned = sum(len(v) for v in assignment.values())
    return {
        "employees": len(employees),
        "available_employees": sum(1 for e in employees if e.availability),
        "shifts": len(shifts),
        "scheduled_hours": sum(shift_hours(s) * len(assignment.get(s.id, [])) for s in shifts),
        "required_staff_total": required,
        "assigned_staff_total": assigned,
        "coverage_ratio": (assigned / required) if required else 1.0,
        "violations": len(solved.violations),
        "feasible": solved.valid and assigned >= required,
        "solver": solved.solver,
    }


def _shift_rows(employees, shifts, assignment) -> List[dict]:
    rows = []
    for s in shifts:
        qualified = sum(1 for e in employees if C.eligible(e, s))
        rows.append({
            "id": s.id, "label": shift_label(s), "day": s.day_of_week, "roles": list(s.required_roles),
            "required": s.required_staff, "qualified": qualified, "assigned": len(assignment.get(s.id, [])),
            "hours": shift_hours(s),
        })
    return rows


def _roster(employees, shifts, assignment) -> List[dict]:
    """Human-readable roster rows (names, not ids) for display."""
    order = {d: i for i, d in enumerate(WEEK_ORDER)}
    who = {e.id: (e.name, e.role) for e in employees}
    rows = []
    for s in sorted(shifts, key=lambda x: (order.get(x.day_of_week, 9), x.start_time)):
        ids = assignment.get(s.id, [])
        base = {"Day": s.day_of_week, "Shift": s.name or shift_label(s), "Time": f"{s.start_time}–{s.end_time}", "Hours": shift_hours(s)}
        for eid in ids:
            name, role = who.get(eid, (eid, "—"))
            rows.append({**base, "Employee": name, "Role": role, "Status": "Assigned"})
        for _ in range(max(0, s.required_staff - len(ids))):
            rows.append({**base, "Employee": "Unfilled", "Role": "—", "Status": "Unfilled"})
    return rows


def _capacity(rows: List[dict]) -> dict:
    """Staff/labor-hour supply vs demand. Available = slots qualified, available staff can fill."""
    required = sum(r["required"] for r in rows)
    available = sum(min(r["required"], r["qualified"]) for r in rows)
    req_h = sum(r["required"] * r["hours"] for r in rows)
    avail_h = sum(min(r["required"], r["qualified"]) * r["hours"] for r in rows)
    return {
        "staff_required": required, "staff_available": available, "staff_shortfall": required - available,
        "hours_required": req_h, "hours_available": avail_h, "hours_shortfall": req_h - avail_h,
    }


def _reason(r: dict) -> str:
    if r["qualified"] == 0:
        return "No qualified employee is available (role, certification or availability)."
    if r["qualified"] < r["required"]:
        return (f"Requires {r['required']} but only {r['qualified']} qualified employee(s) are available. "
                f"Shortfall: {r['required'] - r['qualified']}.")
    return ("Enough qualified employees exist, but weekly-hour, rest or one-shift-per-day limits "
            "prevent full coverage.")


def _shortfalls(rows: List[dict]) -> List[dict]:
    return [
        {"shift": r["label"], "roles": r["roles"] or ["Any role"], "required": r["required"],
         "qualified_available": r["qualified"], "assigned": r["assigned"], "reason": _reason(r)}
        for r in rows if r["assigned"] < r["required"]
    ]


def _role_coverage(roles, shifts, before_asg, after_asg, before_emps, after_emps) -> List[dict]:
    """For each affected role: how many shifts have at least one employee of that role."""
    role_of = {e.id: e.role for e in before_emps + after_emps}
    out = []
    for role in sorted(roles):
        def covered(asg):
            return {s.id for s in shifts if any(role_of.get(i, "").lower() == role.lower() for i in asg.get(s.id, []))}
        b, a = covered(before_asg), covered(after_asg)
        by_id = {s.id: s for s in shifts}
        out.append({"role": role, "before": len(b), "after": len(a),
                    "lost": [shift_label(by_id[i]) for i in sorted(b - a) if i in by_id]})
    return out


def _changes(before_emps, after_emps, after_shifts, before_asg, after_asg) -> dict:
    names = {e.id: e.name for e in before_emps + after_emps}
    by_id = {s.id: s for s in after_shifts}
    hrs = {s.id: shift_hours(s) for s in after_shifts}
    pairs_b = {(e, s) for s, es in before_asg.items() for e in es}
    pairs_a = {(e, s) for s, es in after_asg.items() for e in es}
    added, removed = pairs_a - pairs_b, pairs_b - pairs_a

    def who(asg, sid):
        return ", ".join(sorted(names.get(i, i) for i in asg.get(sid, []))) or "—"

    shift_rows, unchanged = [], 0
    for s in after_shifts:
        b, a = set(before_asg.get(s.id, [])), set(after_asg.get(s.id, []))
        if b == a:
            unchanged += 1
            status, change = "Unchanged", "—"
        else:
            status = "Changed"
            change = "; ".join(filter(None, [
                "Removed: " + ", ".join(sorted(names.get(i, i) for i in b - a)) if b - a else "",
                "Added: " + ", ".join(sorted(names.get(i, i) for i in a - b)) if a - b else "",
            ]))
        shift_rows.append({"shift": shift_label(s), "before": who(before_asg, s.id), "after": who(after_asg, s.id),
                           "status": status, "change": change})

    involved = {e for e, _ in pairs_b} | {e for e, _ in pairs_a}
    emp_rows = []
    for eid in sorted(involved, key=lambda i: names.get(i, i)):
        sb = [s for e, s in pairs_b if e == eid]
        sa = [s for e, s in pairs_a if e == eid]
        gained = [shift_label(by_id[s]) for s in sorted(set(sa) - set(sb)) if s in by_id]
        lost = [shift_label(by_id[s]) for s in sorted(set(sb) - set(sa)) if s in by_id]
        emp_rows.append({
            "employee": names.get(eid, eid),
            "before": f"{len(sb)} shift(s) · {sum(hrs.get(s, 0) for s in sb):.0f}h",
            "after": f"{len(sa)} shift(s) · {sum(hrs.get(s, 0) for s in sa):.0f}h",
            "change": "; ".join(filter(None, ["Gained: " + ", ".join(gained) if gained else "",
                                               "Lost: " + ", ".join(lost) if lost else ""])) or "No change",
            "_moved": bool(gained or lost),
        })
    emp_rows = [r for r in emp_rows if r.pop("_moved")]
    return {
        "shifts": shift_rows, "employees": emp_rows,
        "counts": {
            "shifts_changed": len(after_shifts) - unchanged, "unchanged_shifts": unchanged,
            "employees_reassigned": len({e for e, _ in added}), "employees_removed": len({e for e, _ in removed}),
            "new_assignments": len(added), "removed_assignments": len(removed),
        },
    }


# --------------------------------------------------------------- resolutions --

RESOLUTIONS = {
    "increase_capacity": "Allow overtime (+50% weekly hours)",
    "add_temp_staff": "Add temporary staff",
    "reduce_coverage": "Adjust coverage requirement",
    "increase_max_hours": "Extend weekly hours (+10h)",
    "reassign_multiskilled": "Reassign multi-skilled staff",
}


def relevant_resolutions(understaffed: list, violations: list) -> List[str]:
    keys = []
    if understaffed:
        keys += ["increase_capacity", "add_temp_staff", "reduce_coverage"]
    if any("exceeds max weekly hours" in v for v in violations):
        keys.append("increase_max_hours")
    return keys


def _temp_staff(shifts_under: List[SchedShift], unfilled: Dict[str, int]) -> List[SchedEmployee]:
    """In-memory temporary workers sized to the unfilled slots, grouped by role/certification."""
    groups: Dict[tuple, List[SchedShift]] = {}
    for s in shifts_under:
        role = s.required_roles[0] if s.required_roles else "Temporary Staff"
        groups.setdefault((role, tuple(sorted(c.lower() for c in s.required_certifications))), []).append(s)
    temps, n = [], 0
    for (role, _), group in groups.items():
        per_day: Dict[str, int] = {}
        for s in group:  # one shift per day per person -> size by the busiest day
            per_day[s.day_of_week] = per_day.get(s.day_of_week, 0) + max(unfilled.get(s.id, 1), 1)
        for i in range(max(per_day.values())):
            n += 1
            temps.append(SchedEmployee(
                id=f"TEMP-{n}", name=f"Temporary {role} {i + 1}", role=role, max_weekly_hours=40,
                verified_certifications=list(group[0].required_certifications),
                availability=[(s.day_of_week, s.start_time, s.end_time) for s in group],
            ))
    return temps


def _crosstrain_candidates(employees, shifts_under) -> Dict[str, List[SchedEmployee]]:
    """Employees available + certified for a shift, wrong role, but sharing skills with that role."""
    profile: Dict[str, set] = {}
    for e in employees:
        profile.setdefault(e.role.lower(), set()).update(k.lower() for k in e.skills)
    out = {}
    for s in shifts_under:
        needed = set().union(*(profile.get(r.lower(), set()) for r in s.required_roles)) if s.required_roles else set()
        cands = [e for e in employees
                 if s.required_roles and not C.role_ok(e, s) and C.certs_ok(e, s) and C.is_available(e, s)
                 and needed & {k.lower() for k in e.skills}]
        if cands:
            out[s.id] = cands
    return out


def apply_resolution(resolution_key, employees, shifts, understaffed_ids=None, achieved=None):
    """Returns modified in-memory copies. `understaffed_ids` limits shift-level changes."""
    under = set(understaffed_ids) if understaffed_ids is not None else {s.id for s in shifts}
    achieved = achieved or {}
    if resolution_key == "increase_capacity":
        return [replace(e, max_weekly_hours=round(e.max_weekly_hours * 1.5)) for e in employees], shifts
    if resolution_key == "increase_max_hours":
        return [replace(e, max_weekly_hours=e.max_weekly_hours + 10) for e in employees], shifts
    if resolution_key == "reduce_coverage":
        return employees, [
            replace(s, required_staff=min(s.required_staff, achieved.get(s.id, max(0, s.required_staff - 1))))
            if s.id in under else s for s in shifts
        ]
    if resolution_key == "add_temp_staff":
        target = [s for s in shifts if s.id in under]
        unfilled = {s.id: s.required_staff - achieved.get(s.id, 0) for s in target}
        return employees + _temp_staff(target, unfilled), shifts
    if resolution_key == "reassign_multiskilled":
        target = [s for s in shifts if s.id in under]
        cands = _crosstrain_candidates(employees, target)
        return employees, [
            replace(s, required_roles=sorted(set(s.required_roles) | {e.role for e in cands[s.id]}))
            if s.id in cands else s for s in shifts
        ]
    raise ValueError(f"Unknown resolution: {resolution_key}")


def _resolution_options(employees, shifts, rows, hard_violations) -> List[dict]:
    """Only options that make sense for the detected conflict, each with its expected impact."""
    short = [r for r in rows if r["assigned"] < r["required"]]
    if not short and not hard_violations:
        return []
    opts = []
    limited = [r for r in short if r["qualified"] >= r["required"]]
    if limited or any("exceeds max weekly hours" in v for v in hard_violations):
        n = len(limited)
        opts.append({"key": "increase_capacity", "label": RESOLUTIONS["increase_capacity"],
                     "description": "Raise weekly-hour limits by 50% so qualified employees can absorb the missing shifts.",
                     "expected_impact": f"Targets {n} shift(s) where enough qualified staff exist but hour/rest limits block coverage."})
        opts.append({"key": "increase_max_hours", "label": RESOLUTIONS["increase_max_hours"],
                     "description": "Extend every weekly-hour limit by 10 hours.",
                     "expected_impact": "A smaller overtime allowance for the same hour-limited shifts."})
    under = [s for s in shifts if any(r["id"] == s.id for r in short)]
    if short:
        unfilled = {r["id"]: r["required"] - r["assigned"] for r in short}
        temps = _temp_staff(under, unfilled)
        roles = sorted({t.role for t in temps})
        opts.append({"key": "add_temp_staff", "label": RESOLUTIONS["add_temp_staff"],
                     "description": "Bring in temporary employees with the required role and certifications for the uncovered shifts.",
                     "expected_impact": f"Adds {len(temps)} temporary employee(s) ({', '.join(roles)}) to cover {len(short)} shift(s)."})
        cands = _crosstrain_candidates(employees, under)
        if cands:
            names = sorted({e.name for c in cands.values() for e in c})
            opts.append({"key": "reassign_multiskilled", "label": RESOLUTIONS["reassign_multiskilled"],
                         "description": "Let available employees with matching skills cover shifts outside their usual role.",
                         "expected_impact": f"{len(names)} employee(s) become eligible: {', '.join(names[:6])}{'…' if len(names) > 6 else ''}."})
        slots = sum(r["required"] - r["assigned"] for r in short)
        opts.append({"key": "reduce_coverage", "label": RESOLUTIONS["reduce_coverage"],
                     "description": "Lower the staffing requirement on the uncovered shifts to what can actually be staffed.",
                     "expected_impact": f"Reduces required staff by {slots} slot(s) across {len(short)} shift(s) — accepts a lower service level."})
    return opts


# ------------------------------------------------------------------ pipeline --

def _explain(recoverable, solved, shortfalls) -> str:
    if not solved.valid:
        return "No valid schedule could be produced: " + "; ".join(solved.violations)
    if recoverable:
        return ("The schedule was re-optimized successfully: every shift is covered and all hard constraints "
                "pass independent validation.")
    worst = max(shortfalls, key=lambda s: s["required"] - s["assigned"])
    return (f"No schedule can satisfy all hard constraints with the current workforce. {len(shortfalls)} shift(s) "
            f"cannot be fully staffed — e.g. {worst['shift']}: {worst['reason']}")


def run_simulation(scenario_key: str, employees: List[SchedEmployee], shifts: List[SchedShift],
                   params: Optional[Params] = None) -> dict:
    if scenario_key not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_key}")
    params = params or {}
    label, scenario_fn = SCENARIOS[scenario_key]

    base = solve_schedule(employees, shifts)
    before = _metrics(employees, shifts, base)

    new_emps, new_shifts, note, affected_ids = scenario_fn(employees, shifts, params, base.assignment)
    if new_emps is None:
        return {"scenario": label, "available": False, "message": note, "before": before}

    after_res = solve_schedule(new_emps, new_shifts, prefer=base.assignment)
    after = _metrics(new_emps, new_shifts, after_res)
    rows_b = _shift_rows(employees, shifts, base.assignment)
    rows_a = _shift_rows(new_emps, new_shifts, after_res.assignment)
    shortfalls = _shortfalls(rows_a)
    understaffed = [r["id"] for r in rows_a if r["assigned"] < r["required"]]
    changes = _changes(employees, new_emps, new_shifts, base.assignment, after_res.assignment)
    recoverable = after_res.valid and after_res.fully_covered

    by_emp = {e.id: e for e in employees}
    affected_emps = [{"name": by_emp[i].name, "role": by_emp[i].role} for i in affected_ids if i in by_emp]
    if len(affected_ids) > 5:
        affected_emps = [{"name": f"{len(affected_ids)} employees", "role": "All roles"}]
    new_by_emp = {e.id: e for e in new_emps}
    shift_lookup = {s.id: s for s in new_shifts}
    lost_shifts = {
        sid for sid, es in base.assignment.items() for eid in es
        if eid in set(affected_ids) and sid in shift_lookup and eid in new_by_emp
        and not C.eligible(new_by_emp[eid], shift_lookup[sid])
    }
    req_changed = {a.id for a, b in zip(new_shifts, shifts) if a.required_staff != b.required_staff}
    changed_shifts = {s.id for s in new_shifts if set(base.assignment.get(s.id, [])) != set(after_res.assignment.get(s.id, []))}
    label_by_id = {s.id: shift_label(s) for s in new_shifts}
    affected_shift_ids = [s.id for s in new_shifts if s.id in (lost_shifts | req_changed | changed_shifts)]
    shift_by_id = {s.id: s for s in new_shifts}
    roles = {a["role"] for a in affected_emps if a["role"] != "All roles"}
    for sid in affected_shift_ids:
        roles.update(shift_by_id[sid].required_roles)
    absent_roles = {by_emp[i].role for i in affected_ids if i in by_emp} if len(affected_ids) <= 5 else set()

    cap_b, cap_a = _capacity(rows_b), _capacity(rows_a)
    unfilled_after = after["required_staff_total"] - after["assigned_staff_total"]
    options = _resolution_options(new_emps, new_shifts, rows_a, after_res.violations)

    return {
        "scenario": label, "available": True, "note": note, "params": params,
        "before": before, "after": after,
        "status": "Recoverable" if recoverable else "Infeasible", "recoverable": recoverable,
        "valid": after_res.valid, "solver": after_res.solver, "fallback_reason": after_res.fallback_reason,
        "explanation": _explain(recoverable, after_res, shortfalls),
        "impact": {
            "affected_employees": affected_emps,
            "affected_shifts": [label_by_id[i] for i in affected_shift_ids],
            "affected_roles": sorted(roles),
            "capacity_before": cap_b, "capacity_after": cap_a,
            "unfilled_after": unfilled_after,
            "coverage_before": before["coverage_ratio"], "coverage_after": after["coverage_ratio"],
            "role_coverage": _role_coverage(absent_roles, new_shifts, base.assignment, after_res.assignment, employees, new_emps),
        },
        "changes": changes,
        "roster": _roster(new_emps, new_shifts, after_res.assignment) if after_res.valid else [],
        "shortfalls": shortfalls,
        "resolution_options": options,
        "resolution_keys": [o["key"] for o in options],
        "after_assignments": after_res.assignment,
        "after_violations": after_res.violations,
        "understaffed_shifts": understaffed,
    }


def resolve_simulation(scenario_key: str, resolution_key: str, employees: List[SchedEmployee],
                       shifts: List[SchedShift], params: Optional[Params] = None) -> dict:
    """Re-applies the scenario, applies the chosen resolution on top, re-runs OR-Tools (Greedy only if
    needed) and the independent validator. The result is only reported as verified if validation passes."""
    if scenario_key not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_key}")
    if resolution_key not in RESOLUTIONS:
        raise ValueError(f"Unknown resolution: {resolution_key}")
    params = params or {}
    label, scenario_fn = SCENARIOS[scenario_key]

    base = solve_schedule(employees, shifts)
    scen_emps, scen_shifts, note, _ = scenario_fn(employees, shifts, params, base.assignment)
    if scen_emps is None:
        return {"available": False, "message": note}

    scen = solve_schedule(scen_emps, scen_shifts, prefer=base.assignment)
    before = _metrics(scen_emps, scen_shifts, scen)
    under = [s.id for s in scen_shifts if len(scen.assignment.get(s.id, [])) < s.required_staff]
    achieved = {sid: len(scen.assignment.get(sid, [])) for sid in under}

    res_emps, res_shifts = apply_resolution(resolution_key, scen_emps, scen_shifts, under, achieved)
    solved = solve_schedule(res_emps, res_shifts, prefer=base.assignment)
    after = _metrics(res_emps, res_shifts, solved)
    remaining = [s.id for s in res_shifts if len(solved.assignment.get(s.id, [])) < s.required_staff]
    verified = solved.valid and not remaining
    changes = _changes(employees, res_emps, res_shifts, base.assignment, solved.assignment)
    rows = _shift_rows(res_emps, res_shifts, solved.assignment)

    return {
        "available": True, "scenario": label, "resolution": RESOLUTIONS[resolution_key],
        "before": before, "after": after,
        "feasible": verified, "verified": verified, "valid": solved.valid,
        "solver": solved.solver, "fallback_reason": solved.fallback_reason,
        "assignments": solved.assignment if solved.valid else {},
        "violations": solved.violations, "remaining_understaffed": remaining,
        "remaining_shortfalls": _shortfalls(rows),
        "changes": changes,
        "roster": _roster(res_emps, res_shifts, solved.assignment) if solved.valid else [],
    }
