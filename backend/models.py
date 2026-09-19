"""SQLAlchemy models for the workforce data layer."""

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from backend.database import Base

employee_skills = Table(
    "employee_skills",
    Base.metadata,
    Column("employee_id", Integer, ForeignKey("employees.id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id"), primary_key=True),
)

employee_certifications = Table(
    "employee_certifications",
    Base.metadata,
    Column("employee_id", Integer, ForeignKey("employees.id"), primary_key=True),
    Column("certification_id", Integer, ForeignKey("certifications.id"), primary_key=True),
)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    max_weekly_hours = Column(Integer, nullable=False)
    preferred_shift = Column(String, nullable=True)

    skills = relationship("Skill", secondary=employee_skills, backref="employees")
    certifications = relationship(
        "Certification", secondary=employee_certifications, backref="employees"
    )
    availabilities = relationship(
        "Availability", back_populates="employee", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # verified / unverified / expired. We only store the status - we never
    # claim to authenticate real-world certificates ourselves.
    verification_status = Column(String, nullable=False, default="unverified")
    verification_source = Column(String, nullable=True)


class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    day_of_week = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    employee = relationship("Employee", back_populates="availabilities")


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    day_of_week = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    required_staff = Column(Integer, nullable=False, default=1)
    # Stored as comma-separated strings to keep the schema simple.
    required_roles = Column(String, nullable=True)
    required_certifications = Column(String, nullable=True)
