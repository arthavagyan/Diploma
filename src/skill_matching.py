"""Skill matching: which employees meet ALL requirements of a task.

Rule: an employee qualifies only if, for every required skill, their level is
greater than or equal to the required minimum. A single missing skill or a
single level below the minimum excludes the employee.

Availability (available / busy) is deliberately NOT checked here: it is
handled at the next stage, in the assignment module.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from . import database as db
from .models import Employee, SkillRequirement, Task


@dataclass
class EmployeeCheck:
    """Result of checking one employee against one task."""

    employee: Employee
    reasons: list[str] = field(default_factory=list)  # why the employee was rejected

    @property
    def qualified(self) -> bool:
        return not self.reasons


@dataclass
class MatchReport:
    task: Task
    checks: list[EmployeeCheck]

    @property
    def qualified(self) -> list[Employee]:
        return [c.employee for c in self.checks if c.qualified]

    @property
    def rejected(self) -> list[EmployeeCheck]:
        return [c for c in self.checks if not c.qualified]


def check_employee(employee: Employee, requirements: list[SkillRequirement]) -> list[str]:
    """Return the list of unmet requirements (an empty list means qualified)."""
    reasons: list[str] = []
    for req in requirements:
        level = employee.skills.get(req.skill_name)
        if level is None:
            reasons.append(f"missing skill {req.skill_name} (required >= {req.minimum_level})")
        elif level < req.minimum_level:
            reasons.append(
                f"{req.skill_name} level {level} is below required {req.minimum_level}"
            )
    return reasons


def is_qualified(employee: Employee, requirements: list[SkillRequirement]) -> bool:
    return not check_employee(employee, requirements)


def match_employees(task: Task, employees: list[Employee]) -> MatchReport:
    """Check every employee against the task requirements (pure function, no DB)."""
    checks = [
        EmployeeCheck(employee=e, reasons=check_employee(e, task.requirements))
        for e in sorted(employees, key=lambda e: e.id)
    ]
    return MatchReport(task=task, checks=checks)


def find_qualified_employees(conn: sqlite3.Connection, task_id: int) -> MatchReport:
    """Load the task and all employees from the database and run the check."""
    task = db.get_task(conn, task_id)
    if task is None:
        raise ValueError(f"Task #{task_id} not found")
    return match_employees(task, db.list_employees(conn))
