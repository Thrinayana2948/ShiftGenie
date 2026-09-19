# ShiftGenie

An AI-assisted workforce scheduling platform for retail. Managers describe
staffing requirements in natural language; ShiftGenie turns that into a
verified schedule and lets them stress-test the workforce against
disruptions before committing to it.

**Product flow:** Generate → Validate → Simulate → Resolve

## Architecture

- **Frontend:** Streamlit — pages for Overview, Generate, Schedule, Validate, Simulate, Workforce.
- **Backend:** FastAPI — all business logic lives here; the frontend only calls its API.
- **Database:** Supabase PostgreSQL via SQLAlchemy (no SQLite in the runtime path).
- **AI (Gemini):** understands natural-language requirements only. It converts text into a
  structured, Pydantic-validated `ParsedRequirement`. **It never generates or modifies a schedule.**
- **Scheduling (OR-Tools):** the CP-SAT solver assigns employees to shifts, respecting roles,
  certifications, availability, rest periods, and weekly-hour caps. Falls back to a
  greedy Python solver if OR-Tools is unavailable.
- **Validation:** a deterministic Python validator re-checks every generated schedule
  against hard constraints. A schedule is only ever reported "feasible" if the validator
  confirms it — the optimizer's own output is never trusted blindly.
- **Simulation:** what-if scenarios (employee call-outs, demand spikes, reduced capacity)
  run on in-memory copies of the workforce data and re-invoke the same scheduler/validator.
  The database is never written to during simulation.
- **Resolution:** for infeasible simulations, candidate fixes (more hours, temp staff,
  reduced coverage) are actually re-run through the scheduler + validator to verify
  whether they work — never just asserted.

## Setup

### 1. Configure environment variables

Copy `.env.example` to `.env`:

```
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.<project>.supabase.co:5432/postgres
BACKEND_URL=http://127.0.0.1:8000
GEMINI_API_KEY=<your Gemini API key>
```

`GEMINI_API_KEY` is read server-side only (`backend/services/gemini_provider.py`) and is
never sent to or exposed in the frontend. `.env` is gitignored.

### 2. Virtual environment + dependencies

```bash
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```

### 3. Run the backend

```bash
uvicorn backend.main:app --reload
```

Verify: `GET http://127.0.0.1:8000/health`

### 4. Run the frontend

```bash
streamlit run frontend/app.py
```

### 5. Run tests

```bash
pytest
```

Tests use an isolated in-memory SQLite database and mocked Gemini responses — they never
touch Supabase or spend Gemini API credits.

## Demo Data

`sample_data/demo_scenario.json` — "Demo Scenario — Synthetic Retail Workforce Data":
28 fictional retail employees (supervisors, cashiers, sales floor, stock/inventory) and
14 demo shifts. Load it via the Workforce page's "Load Demo Scenario" button, or
`POST /demo/load` — safe to call repeatedly; it skips records that already exist and
never overwrites user-added employees.

See `docs/DEMO_CHECKLIST.md` for a full walkthrough.

## Key API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend liveness |
| `GET/POST/PUT/DELETE /employees[/{id}]` | Employee CRUD |
| `GET/POST /shifts` | Shift CRUD |
| `POST /demo/load` | Load synthetic demo workforce (idempotent) |
| `POST /demo/reset` | Restore the demo workforce/shifts to the synthetic baseline (user-created employees untouched) |
| `POST /schedule/generate` | Run OR-Tools + validator over current DB data |
| `POST /requirements/parse` | Gemini: text → structured `ParsedRequirement` only |
| `POST /requirements/schedule` | Gemini parses text → OR-Tools generates schedule → validator checks it |
| `GET /schedule/simulate/scenarios` | List available what-if scenarios |
| `POST /schedule/simulate` | Run a what-if scenario (in-memory only) |
| `POST /schedule/resolve` | Test a resolution against a scenario's conflict |

## Project Structure

```
ShiftGenie/
├── backend/
│   ├── main.py              # FastAPI routes
│   ├── models.py, schemas.py, crud.py, database.py
│   ├── load_demo_data.py
│   └── services/
│       ├── gemini_provider.py, ai_service.py   # requirement understanding only
│       ├── scheduler.py, scheduler_types.py    # OR-Tools + greedy fallback
│       ├── validator.py                        # deterministic hard-constraint checks
│       ├── requirement_pipeline.py              # ParsedRequirement -> shifts -> schedule
│       ├── simulation.py                        # what-if scenarios + resolutions
│       └── benchmark_adapter.py                 # public benchmark instance support
├── frontend/app.py           # Streamlit UI
├── sample_data/              # demo workforce + benchmark instances
├── tests/                    # pytest, mocked Gemini, isolated SQLite
├── docs/DEMO_CHECKLIST.md
└── .env.example
```
