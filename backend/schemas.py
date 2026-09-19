"""Pydantic schemas for request/response validation."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ParsedRequirement(BaseModel):
    """Structured scheduling requirement extracted from natural language by Gemini."""

    staffing_count: Optional[int] = None
    roles: List[str] = []
    skills: List[str] = []
    required_certifications: List[str] = []
    days: List[str] = []
    shift_start_time: Optional[str] = None
    shift_end_time: Optional[str] = None
    max_hours: Optional[int] = None
    min_rest_hours: Optional[int] = None
    preferences: List[str] = []
    notes: Optional[str] = None


class RequirementParseRequest(BaseModel):
    text: str


class SimulationRequest(BaseModel):
    scenario: str
    params: Optional[dict] = None


class ResolveRequest(BaseModel):
    scenario: str
    resolution: str
    params: Optional[dict] = None


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CertificationIn(BaseModel):
    name: str
    verification_status: str = "unverified"  # verified / unverified / expired
    verification_source: Optional[str] = None


class CertificationOut(CertificationIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AvailabilityIn(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str


class AvailabilityOut(AvailabilityIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EmployeeIn(BaseModel):
    name: str
    role: str
    max_weekly_hours: int
    preferred_shift: Optional[str] = None
    skills: List[str] = []
    certifications: List[CertificationIn] = []
    availability: List[AvailabilityIn] = []


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    role: str
    max_weekly_hours: int
    preferred_shift: Optional[str] = None
    skills: List[SkillOut] = []
    certifications: List[CertificationOut] = []
    availabilities: List[AvailabilityOut] = []


class ShiftIn(BaseModel):
    name: str
    day_of_week: str
    start_time: str
    end_time: str
    required_staff: int = 1
    required_roles: List[str] = []
    required_certifications: List[str] = []


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    day_of_week: str
    start_time: str
    end_time: str
    required_staff: int
    required_roles: List[str] = []
    required_certifications: List[str] = []
