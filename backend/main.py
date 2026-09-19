"""ShiftGenie FastAPI backend."""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from backend import crud, models, schemas
from backend.database import Base, engine, get_db
from backend.load_demo_data import load_demo_data, reset_demo_data
from backend.services.ai_service import parse_requirement
from backend.services.requirement_pipeline import generate_schedule_from_requirement
from backend.services.scheduler import solve_schedule
from backend.services.scheduler_types import from_db, shift_hours
from backend.services.simulation import SCENARIOS, resolve_simulation, run_simulation

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ShiftGenie API")


@app.get("/health")
def health():
    """Confirm the backend is running."""
    return {"status": "ok", "message": "ShiftGenie backend is running"}


@app.get("/employees", response_model=list[schemas.EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return crud.get_employees(db)


@app.post("/employees", response_model=schemas.EmployeeOut)
def add_employee(employee: schemas.EmployeeIn, db: Session = Depends(get_db)):
    return crud.create_employee(db, employee)


@app.get("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = crud.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.put("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def edit_employee(
    employee_id: int, employee: schemas.EmployeeIn, db: Session = Depends(get_db)
):
    existing = crud.get_employee(db, employee_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    return crud.update_employee(db, existing, employee)


@app.delete("/employees/{employee_id}")
def remove_employee(employee_id: int, db: Session = Depends(get_db)):
    existing = crud.get_employee(db, employee_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    crud.delete_employee(db, existing)
    return {"status": "deleted", "id": employee_id}


@app.get("/shifts", response_model=list[schemas.ShiftOut])
def list_shifts(db: Session = Depends(get_db)):
    return [crud.shift_to_out(s) for s in crud.get_shifts(db)]


@app.post("/shifts", response_model=schemas.ShiftOut)
def add_shift(shift: schemas.ShiftIn, db: Session = Depends(get_db)):
    return crud.shift_to_out(crud.create_shift(db, shift))


@app.post("/demo/load")
def load_demo(db: Session = Depends(get_db)):
    """Load the synthetic 24-person demo scenario. Safe to call repeatedly:
    existing employees/shifts (including user-created ones) are left untouched."""
    return load_demo_data(db)


@app.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    """Restore the synthetic demo workforce/shifts to the baseline (user-created employees untouched)."""
    return reset_demo_data(db)


@app.post("/schedule/generate")
def generate(db: Session = Depends(get_db)):
    """OR-Tools (Greedy fallback) over all employees/shifts in the database; the independent
    validator gates the result."""
    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    solved = solve_schedule(sched_employees, sched_shifts)
    by_shift = {s.id: s for s in sched_shifts}
    hours = {}
    for sid, eids in solved.assignment.items():
        for eid in eids:
            hours[eid] = hours.get(eid, 0.0) + shift_hours(by_shift[sid])
    overtime = sum(max(0.0, h - e.max_weekly_hours) for e in sched_employees for h in [hours.get(e.id, 0.0)])
    required = sum(s.required_staff for s in sched_shifts)
    assigned = sum(len(v) for v in solved.assignment.values())
    return {
        "assignments": solved.assignment,
        "violations": solved.violations,
        "valid": solved.valid,
        "fully_covered": solved.fully_covered,
        "solver": solved.solver,
        "fallback_reason": solved.fallback_reason,
        "stats": {
            "employees": len(sched_employees), "shifts": len(sched_shifts), "assignments": assigned,
            "required": required, "coverage_ratio": (assigned / required) if required else 1.0,
            "violations": len(solved.violations), "overtime_hours": overtime,
        },
    }


@app.post("/requirements/parse", response_model=schemas.ParsedRequirement)
def parse_requirement_endpoint(req: schemas.RequirementParseRequest):
    """Gemini extracts structured requirements only; it does not generate schedules."""
    try:
        return parse_requirement(req.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/requirements/schedule")
def schedule_from_requirement(req: schemas.RequirementParseRequest, db: Session = Depends(get_db)):
    """Natural language -> Gemini (parse only) -> shifts -> OR-Tools/greedy -> validator."""
    try:
        parsed = parse_requirement(req.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    known_certs = {c.name for e in employees for c in e.certifications}
    result = generate_schedule_from_requirement(parsed, sched_employees, sched_shifts, known_certs)
    result["parsed_requirement"] = parsed.model_dump()
    return result


@app.get("/schedule/simulate/scenarios")
def list_scenarios():
    return {key: label for key, (label, _) in SCENARIOS.items()}


@app.post("/schedule/simulate")
def simulate(payload: schemas.SimulationRequest, db: Session = Depends(get_db)):
    """Runs a what-if scenario on in-memory copies of DB data. Never writes to the database."""
    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    try:
        return run_simulation(payload.scenario, sched_employees, sched_shifts, payload.params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/schedule/resolve")
def resolve(payload: schemas.ResolveRequest, db: Session = Depends(get_db)):
    """Applies a resolution on top of a scenario and reruns OR-Tools + validator to verify it. No database writes."""
    employees = crud.get_employees(db)
    shifts = [crud.shift_to_out(s) for s in crud.get_shifts(db)]
    sched_employees, sched_shifts = from_db(employees, shifts)
    try:
        return resolve_simulation(payload.scenario, payload.resolution, sched_employees, sched_shifts, payload.params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
