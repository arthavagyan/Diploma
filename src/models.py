"""Domain data model.

Entity classes do not depend on the database: they can be created by hand
(e.g. in tests) and passed directly to the skill-matching functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EmployeeStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    COMPLETED = "completed"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def weight(self) -> int:
        """Preliminary priority weight w_j for the future objective function.

        Not used by the current baseline assignment rule.
        """
        return {"low": 1, "medium": 2, "high": 3}[self.value]


@dataclass(frozen=True)
class SkillRequirement:
    """Task requirement: a skill and the minimum acceptable level (1-5)."""

    skill_name: str
    minimum_level: int


@dataclass
class Employee:
    id: int
    full_name: str
    status: EmployeeStatus
    # skill name -> proficiency level (1-5)
    skills: dict[str, int] = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        return self.status == EmployeeStatus.AVAILABLE


@dataclass
class Task:
    id: int
    title: str
    description: str
    priority: Priority
    estimated_duration: int  # estimated duration, minutes
    status: TaskStatus
    created_at: str
    requirements: list[SkillRequirement] = field(default_factory=list)


@dataclass
class AssignmentRecord:
    """An Assignments row joined with task title and employee name for display."""

    id: int
    task_id: int
    task_title: str
    employee_id: int
    employee_name: str
    assigned_at: str
    status: AssignmentStatus
