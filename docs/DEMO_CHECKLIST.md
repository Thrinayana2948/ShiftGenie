# ShiftGenie Demo Checklist

## Startup

```bash
uvicorn backend.main:app --reload      # terminal 1
streamlit run frontend/app.py          # terminal 2
```

Confirm: Overview page loads, "Backend Connection Status" (or health check) is green.

## 1. Load Demo Data

Workforce page → **Load Demo Scenario**.
Expected: 28 employees, 14 shifts. Safe to click again — it skips existing records.

## 2. Requirement → Schedule (Generate page)

Enter: *"I need 3 cashiers and 1 supervisor every Saturday and Sunday from 4 PM to 10 PM."*
Click **Generate Schedule**.
Expected: Structured Requirements panel shows parsed fields (roles, days, time window).
Note: this is the only step that calls Gemini — don't repeat it needlessly (limited free credits).

## 3. Validation (Schedule + Validate pages)

Schedule page → **Generate Schedule (full demo shifts)** → Validate page.
Expected: Schedule Health = VALID (0 violations) with the current demo data; all 6 checks
(Availability, Coverage, Required Roles, Certifications, Rest Periods, Weekly Hours) show Satisfied.

## 4. Conflict / Infeasibility Demo

Simulate page → select **Reduce Staff Capacity** or **Supervisor Unavailable** → **Run Simulation**.
Expected: BEFORE/AFTER metrics differ; if infeasible, Schedule Health = CONFLICT DETECTED with real
violation text (no invented explanations).

## 5. Simulation Demo

Try each scenario in turn: Rahul Call-Out, Priya Call-Out, +20% Weekend Demand,
Supervisor Unavailable, Reduce Staff Capacity.
Expected: real before/after numbers (employees, hours, coverage, violations) computed from
an actual OR-Tools re-run — not canned values.

## 6. Resolution Demo

After an infeasible simulation, pick a suggested **Resolution Option** → **Test Resolution**.
Expected: RESOLUTION VERIFIED (validator confirms feasible) or RESOLUTION NOT SUFFICIENT
(remaining conflict shown) — the actual verified outcome, not a guess.

## Expected Outcomes Summary

| Step | Expected |
|---|---|
| Demo load | 28 employees, 14 shifts, idempotent |
| Full schedule generate | 0 violations |
| Simulation | Real before/after deltas; DB unchanged after |
| Resolution | Verified or Not Sufficient, backed by scheduler+validator |

## Final Pre-Presentation Checks

- [ ] Backend running, `/health` returns 200
- [ ] Demo data loaded (28 employees / 14 shifts)
- [ ] One Generate call rehearsed (don't over-call Gemini)
- [ ] Light and dark mode both look correct
- [ ] Employee count in Supabase matches what the UI shows after a fresh backend restart
- [ ] `pytest` passes (44/44 at last check)
