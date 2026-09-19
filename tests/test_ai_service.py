from unittest.mock import patch

import pytest

from backend.schemas import ParsedRequirement
from backend.services.ai_service import parse_requirement


def test_schema_defaults():
    r = ParsedRequirement()
    assert r.roles == [] and r.staffing_count is None


@patch("backend.services.ai_service.gemini_provider.call_gemini")
def test_parse_requirement_two_examples(mock_call):
    mock_call.return_value = (
        '{"staffing_count": 3, "roles": ["Cashier"], "skills": ["Cash Handling"], '
        '"required_certifications": ["Food Safety"], "days": ["Monday", "Tuesday"], '
        '"shift_start_time": "09:00", "shift_end_time": "17:00", "max_hours": 40, '
        '"min_rest_hours": 8, "preferences": ["morning"], "notes": null}'
    )
    result = parse_requirement("Need 3 cashiers Mon/Tue 9-5 with food safety cert")
    assert result.staffing_count == 3
    assert result.roles == ["Cashier"]
    assert result.days == ["Monday", "Tuesday"]

    mock_call.return_value = (
        '{"staffing_count": 2, "roles": ["Supervisor"], "skills": [], '
        '"required_certifications": [], "days": ["Saturday", "Sunday"], '
        '"shift_start_time": "10:00", "shift_end_time": "18:00", "max_hours": 30, '
        '"min_rest_hours": 10, "preferences": [], "notes": "weekend coverage"}'
    )
    result2 = parse_requirement("2 supervisors for weekend coverage 10-6")
    assert result2.staffing_count == 2
    assert result2.days == ["Saturday", "Sunday"]


@patch("backend.services.ai_service.gemini_provider.call_gemini")
def test_malformed_json_rejected(mock_call):
    mock_call.return_value = "not json at all"
    with pytest.raises(ValueError):
        parse_requirement("anything")


@patch("backend.services.ai_service.gemini_provider.call_gemini")
def test_schema_mismatch_rejected(mock_call):
    mock_call.return_value = '{"staffing_count": "three"}'
    with pytest.raises(ValueError):
        parse_requirement("anything")


@patch("backend.services.ai_service.gemini_provider.call_gemini")
def test_gemini_failure_handled_gracefully(mock_call):
    mock_call.side_effect = RuntimeError("API down")
    with pytest.raises(ValueError):
        parse_requirement("anything")
