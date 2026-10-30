"""Baseline (demonstration) assignment mechanism.

This is a simple deterministic rule used to demonstrate the workflow.
It is NOT an optimal or optimised distribution of tasks.

Steps:
1. Find employees who meet the skill requirements (skill_matching).
2. Keep only those who are currently available.
3. If there are any, pick one with the selection strategy
   (default: the lowest employee ID).
4. If all qualified employees are busy, the task stays in the queue (pending).
5. If nobody is qualified at all, report it separately.
6. On success, in one transaction: employee -> busy, task -> assigned,
   new row in Assignments.

The selection rule is isolated behind the SelectionStrategy interface, so a
future optimisation module can replace it without touching the rest of the code.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from . import database as db
from .models import AssignmentRecord, Employee, Task, TaskStatus
from .skill_matching import MatchReport, find_qualified_employees, is_qualified


class AssignmentError(Exception):
    """Base class for assignment errors."""


class EmployeeBusyError(AssignmentError):
    """The employee already has an active task."""


class TaskNotPendingError(AssignmentError):
    """The task is not in the pending state."""


class NotQualifiedError(AssignmentError):
    """The employee does not meet the task requirements."""


class AssignmentOutcome(StrEnum):
    ASSIGNED = "assigned"                # an employee was assigned
    ALL_QUALIFIED_BUSY = "queued"        # qualified employees exist but all are busy
    NO_QUALIFIED = "no_qualified"        # nobody meets the requirements
    NOT_PENDING = "not_pending"          # task is already assigned or completed


@dataclass
class AssignmentResult:
    outcome: AssignmentOutcome
    task: Task
    message: str
    employee: Employee | None = None
    report: MatchReport | None = None


class SelectionStrategy(Protocol):
    """Chooses one employee from available, qualified candidates."""

    description: str

    def select(self, task: Task, candidates: list[Employee]) -> Employee: ...


class LowestIdStrategy:
    """Baseline rule: the available qualified employee with the lowest ID.

    Deterministic and easy to explain; not optimal.
    """

    description = "baseline rule: lowest ID among available qualified employees"

    def select(self, task: Task, candidates: list[Employee]) -> Employee:
        return min(candidates, key=lambda e: e.id)


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def assign_employee_to_task(conn: sqlite3.Connection, task_id: int, employee_id: int) -> None:
    """Assign a specific employee to a task with all safety checks.

    Raises an AssignmentError subclass instead of creating an invalid state.
    Everything happens in a single transaction.
    """
    task = db.get_task(conn, task_id)
    employee = db.get_employee(conn, employee_id)
    if task is None:
        raise ValueError(f"Task #{task_id} not found")
    if employee is None:
        raise ValueError(f"Employee #{employee_id} not found")
    if not is_qualified(employee, task.requirements):
        raise NotQualifiedError(f"{employee.full_name} does not meet the requirements of task #{task_id}")

    try:
        with conn:  # commit on success, rollback on any exception
            cur = conn.execute(
                "UPDATE Employees SET status = 'busy' WHERE id = ? AND status = 'available'",
                (employee_id,),
            )
            if cur.rowcount != 1:
                raise EmployeeBusyError(f"{employee.full_name} is already busy with another task")
            cur = conn.execute(
                "UPDATE Tasks SET status = 'assigned' WHERE id = ? AND status = 'pending'",
                (task_id,),
            )
            if cur.rowcount != 1:
                raise TaskNotPendingError(f"Task #{task_id} is not pending")
            conn.execute(
                "INSERT INTO Assignments (task_id, employee_id, assigned_at, status) "
                "VALUES (?, ?, ?, 'active')",
                (task_id, employee_id, _now()),
            )
    except sqlite3.IntegrityError as exc:
        # Last line of defence: the partial unique indexes in the schema.
        raise EmployeeBusyError(f"Double assignment blocked by the database: {exc}") from exc


def assign_task(
    conn: sqlite3.Connection, task_id: int, strategy: SelectionStrategy | None = None
) -> AssignmentResult:
    """Try to assign a task using the baseline rule (or a given strategy)."""
    strategy = strategy or LowestIdStrategy()
    report = find_qualified_employees(conn, task_id)
    task = report.task

    if task.status != TaskStatus.PENDING:
        return AssignmentResult(
            AssignmentOutcome.NOT_PENDING, task,
            f"Task #{task.id} has status '{task.status}', nothing to assign.", report=report,
        )

    if not report.qualified:
        return AssignmentResult(
            AssignmentOutcome.NO_QUALIFIED, task,
            f"No employee meets the requirements of task #{task.id}. "
            "The task stays pending; a suitable specialist is needed.",
            report=report,
        )

    available = [e for e in report.qualified if e.is_available]
    if not available:
        names = ", ".join(e.full_name for e in report.qualified)
        return AssignmentResult(
            AssignmentOutcome.ALL_QUALIFIED_BUSY, task,
            f"Qualified employees exist ({names}), but all of them are busy. "
            f"Task #{task.id} stays in the queue with status 'pending'.",
            report=report,
        )

    chosen = strategy.select(task, available)
    assign_employee_to_task(conn, task.id, chosen.id)
    return AssignmentResult(
        AssignmentOutcome.ASSIGNED,
        db.get_task(conn, task.id),
        f"Task #{task.id} assigned to {chosen.full_name} ({strategy.description}).",
        employee=db.get_employee(conn, chosen.id),
        report=report,
    )


def complete_task(conn: sqlite3.Connection, task_id: int) -> AssignmentRecord:
    """Mark an assigned task as completed and free its employee."""
    active = [a for a in db.list_assignments(conn, only_active=True) if a.task_id == task_id]
    if not active:
        raise TaskNotPendingError(f"Task #{task_id} has no active assignment")
    record = active[0]
    with conn:
        conn.execute("UPDATE Assignments SET status = 'completed' WHERE id = ?", (record.id,))
        conn.execute("UPDATE Tasks SET status = 'completed' WHERE id = ?", (task_id,))
        conn.execute(
            "UPDATE Employees SET status = 'available' WHERE id = ?", (record.employee_id,)
        )
    return record
