"""Console menu for demonstrating the prototype."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import database as db
from .assignment import AssignmentError, assign_task, complete_task
from .models import SkillRequirement
from .skill_matching import MatchReport, find_qualified_employees

SHORT_SKILL_NAMES = {"System Administration": "SysAdmin"}

MENU = """
================ Task Assignment Prototype ================
 1. Employees and their skills
 2. Tasks and their requirements
 3. Check qualification for a task
 4. Assign a task (baseline rule)
 5. Assignment log
 6. Complete a task (frees the employee)
 7. Reset database to demo data
 0. Exit
==========================================================="""


def short(skill: str) -> str:
    return SHORT_SKILL_NAMES.get(skill, skill)


def format_requirements(requirements: list[SkillRequirement]) -> str:
    if not requirements:
        return "(no requirements)"
    return ", ".join(f"{r.skill_name} >= {r.minimum_level}" for r in requirements)


def print_employees(conn: sqlite3.Connection) -> None:
    employees = db.list_employees(conn)
    skills = db.list_skills(conn)
    print("\nEmployees (skill levels 1-5, '-' = no skill)\n")
    header = f"{'ID':>3}  {'Name':<18} {'Status':<10}" + "".join(
        f"{short(s):>12}" for s in skills
    )
    print(header)
    print("-" * len(header))
    for e in employees:
        row = f"{e.id:>3}  {e.full_name:<18} {e.status:<10}" + "".join(
            f"{e.skills.get(s, '-'):>12}" for s in skills
        )
        print(row)
    print("\nSysAdmin = System Administration")


def print_tasks(conn: sqlite3.Connection) -> None:
    print("\nTasks\n")
    header = f"{'ID':>3}  {'Title':<36} {'Priority':<9} {'Min':>4}  {'Status':<10} Requirements"
    print(header)
    print("-" * (len(header) + 20))
    for t in db.list_tasks(conn):
        print(
            f"{t.id:>3}  {t.title:<36} {t.priority:<9} {t.estimated_duration:>4}  "
            f"{t.status:<10} {format_requirements(t.requirements)}"
        )
    print("\nMin = estimated duration in minutes")


def print_match_report(report: MatchReport) -> None:
    t = report.task
    print(f"\nTask #{t.id}: {t.title}")
    print(f"Requirements: {format_requirements(t.requirements)}")
    print("\nQualified employees (availability is not considered at this step):")
    if report.qualified:
        for e in report.qualified:
            print(f"  [+] {e.full_name:<18} status: {e.status}")
    else:
        print("  (none)")
    print("\nNot qualified:")
    if report.rejected:
        for c in report.rejected:
            print(f"  [-] {c.employee.full_name:<18} " + "; ".join(c.reasons))
    else:
        print("  (none)")


def print_assignments(conn: sqlite3.Connection) -> None:
    records = db.list_assignments(conn)
    print("\nAssignments\n")
    if not records:
        print("  (no assignments yet)")
        return
    header = f"{'ID':>3}  {'Task':<42} {'Employee':<18} {'Assigned at':<20} Status"
    print(header)
    print("-" * len(header))
    for a in records:
        task = f"#{a.task_id} {a.task_title}"
        print(f"{a.id:>3}  {task:<42} {a.employee_name:<18} {a.assigned_at:<20} {a.status}")


def ask_int(prompt: str) -> int | None:
    raw = input(prompt).strip()
    if not raw.isdigit():
        print("Please enter a number.")
        return None
    return int(raw)


def run(db_path: str | Path = db.DEFAULT_DB_PATH) -> None:
    conn = db.init_database(db_path)
    print(f"Database: {db_path}")
    try:
        while True:
            print(MENU)
            choice = input("Choose an option: ").strip()
            try:
                if choice == "1":
                    print_employees(conn)
                elif choice == "2":
                    print_tasks(conn)
                elif choice == "3":
                    task_id = ask_int("Task ID: ")
                    if task_id is not None:
                        print_match_report(find_qualified_employees(conn, task_id))
                elif choice == "4":
                    task_id = ask_int("Task ID: ")
                    if task_id is not None:
                        result = assign_task(conn, task_id)
                        if result.report:
                            print_match_report(result.report)
                        print(f"\nResult [{result.outcome}]: {result.message}")
                elif choice == "5":
                    print_assignments(conn)
                elif choice == "6":
                    task_id = ask_int("Task ID to complete: ")
                    if task_id is not None:
                        record = complete_task(conn, task_id)
                        print(f"\nTask #{task_id} completed. {record.employee_name} is available again.")
                elif choice == "7":
                    conn.close()
                    conn = db.reset_database(db_path)
                    print("\nDatabase reset to the initial demo data.")
                elif choice == "0":
                    print("Bye!")
                    break
                else:
                    print("Unknown option.")
            except (ValueError, AssignmentError) as exc:
                print(f"\nError: {exc}")
            if choice != "0":
                input("\nPress Enter to continue...")
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
    finally:
        conn.close()
