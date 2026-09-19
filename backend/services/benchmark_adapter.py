"""Converts public shift-scheduling benchmark instances (see
sample_data/benchmarks/README.md for the expected JSON shape) into
ShiftGenie's internal scheduling representation, isolated from the main
demo/live data path.
"""

import json
from pathlib import Path
from typing import List, Tuple

from backend.services.scheduler_types import SchedEmployee, SchedShift

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data" / "benchmarks"


def load_benchmark_instance(filename: str) -> Tuple[List[SchedEmployee], List[SchedShift]]:
    path = BENCHMARKS_DIR / filename
    data = json.loads(path.read_text())

    employees = [
        SchedEmployee(
            id=e["id"],
            name=e["id"],
            role="Benchmark",
            max_weekly_hours=e["max_weekly_hours"],
            availability=[tuple(a) for a in e.get("availability", [])],
        )
        for e in data["employees"]
    ]
    shifts = [
        SchedShift(
            id=s["id"],
            day_of_week=s["day"],
            start_time=s["start"],
            end_time=s["end"],
            required_staff=s.get("required_staff", 1),
        )
        for s in data["shifts"]
    ]
    return employees, shifts
