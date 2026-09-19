"""AI requirement-extraction service. Gemini only converts natural language
into a validated ParsedRequirement; it never generates schedules or bypasses
OR-Tools/the validator. Fails safely if Gemini is unavailable or returns bad JSON.
"""

import json
import re

from pydantic import ValidationError

from backend.schemas import ParsedRequirement
from backend.services import gemini_provider


def parse_requirement(text: str) -> ParsedRequirement:
    """Raises ValueError on any failure (missing key, bad JSON, schema mismatch)."""
    try:
        raw = gemini_provider.call_gemini(text)
    except Exception as e:
        raise ValueError(f"Gemini request failed: {e}")

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("Gemini did not return JSON")

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}")

    try:
        return ParsedRequirement(**data)
    except ValidationError as e:
        raise ValueError(f"Gemini output did not match schema: {e}")
