# Benchmark Instances

This folder holds small **public shift-scheduling benchmark** instances used
only to stress-test the optimizer independently of the ShiftGenie demo data.
They are not related to the retail demo workforce.

## Format expected by `backend/services/benchmark_adapter.py`

Each instance is a single JSON file shaped like `sample_small_7day.json`:

```json
{
  "employees": [
    {"id": "E1", "max_weekly_hours": 40, "availability": [["Mon", "08:00", "16:00"]]}
  ],
  "shifts": [
    {"id": "S1", "day": "Mon", "start": "08:00", "end": "16:00", "required_staff": 2}
  ]
}
```

- `availability` entries are `[day, start_time, end_time]`.
- Real published multi-activity/multi-day benchmark sets (e.g. the Van den
  Bergh et al. personnel scheduling benchmark instances, or similar public
  shift-scheduling datasets) are not bundled here to avoid a complex
  downloader. To use one, convert it to the JSON shape above and place the
  file in this folder — the adapter only needs `employees` and `shifts` in
  this format, it does not care about the original source format.
- `sample_small_7day.json` is a small hand-built 7-day instance included so
  the adapter and optimizer can be exercised without any external download.
