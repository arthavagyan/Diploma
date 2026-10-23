"""SQLite access layer: schema, demo data and entity loading."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import (
    AssignmentRecord,
    AssignmentStatus,
    Employee,
    EmployeeStatus,
    Priority,
    SkillRequirement,
    Task,
    TaskStatus,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "tasks.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS Employees (
    id         INTEGER PRIMARY KEY,
    full_name  TEXT    NOT NULL UNIQUE,
    status     TEXT    NOT NULL DEFAULT 'available'
               CHECK (status IN ('available', 'busy'))
);

CREATE TABLE IF NOT EXISTS Skills (
    id    INTEGER PRIMARY KEY,
    name  TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS EmployeeSkills (
    employee_id        INTEGER NOT NULL REFERENCES Employees(id) ON DELETE CASCADE,
    skill_id           INTEGER NOT NULL REFERENCES Skills(id)    ON DELETE CASCADE,
    proficiency_level  INTEGER NOT NULL CHECK (proficiency_level BETWEEN 1 AND 5),
    PRIMARY KEY (employee_id, skill_id)
);

CREATE TABLE IF NOT EXISTS Tasks (
    id                  INTEGER PRIMARY KEY,
    title               TEXT    NOT NULL UNIQUE,
    description         TEXT    NOT NULL DEFAULT '',
    priority            TEXT    NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
    estimated_duration  INTEGER NOT NULL CHECK (estimated_duration > 0),  -- minutes
    status              TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'assigned', 'completed')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS TaskRequirements (
    task_id        INTEGER NOT NULL REFERENCES Tasks(id)  ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES Skills(id) ON DELETE CASCADE,
    minimum_level  INTEGER NOT NULL CHECK (minimum_level BETWEEN 1 AND 5),
    PRIMARY KEY (task_id, skill_id)
);

CREATE TABLE IF NOT EXISTS Assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES Tasks(id),
    employee_id  INTEGER NOT NULL REFERENCES Employees(id),
    assigned_at  TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'completed'))
);

-- Database-level guard: an employee has at most one active assignment,
-- a task has at most one active assignee (prototype limitation).
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_assignment_employee
    ON Assignments(employee_id) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_assignment_task
    ON Assignments(task_id) WHERE status = 'active';
"""

# --- Demo data (fixed IDs => re-running never creates duplicates) ---

DEMO_SKILLS = [
    (1, "Python"),
    (2, "SQL"),
    (3, "JavaScript"),
    (4, "Networking"),
    (5, "System Administration"),
]

DEMO_EMPLOYEES = [
    (1, "Arman Petrosyan"),
    (2, "David Sargsyan"),
    (3, "Karen Hakobyan"),
    (4, "Anna Grigoryan"),
    (5, "Tigran Hovsepyan"),
    (6, "Mariam Vardanyan"),
]

# (employee_id, skill_id, proficiency_level)
DEMO_EMPLOYEE_SKILLS = [
    (1, 1, 5), (1, 2, 3), (1, 3, 2),   # Arman: Python 5, SQL 3, JavaScript 2
    (2, 1, 3), (2, 2, 5), (2, 4, 2),   # David: Python 3, SQL 5, Networking 2
    (3, 1, 4), (3, 2, 4), (3, 5, 3),   # Karen: Python 4, SQL 4, SysAdmin 3
    (4, 3, 5), (4, 2, 3), (4, 1, 2),   # Anna: JavaScript 5, SQL 3, Python 2
    (5, 4, 5), (5, 5, 5), (5, 1, 2),   # Tigran: Networking 5, SysAdmin 5, Python 2
    (6, 4, 3), (6, 5, 4), (6, 2, 2),   # Mariam: Networking 3, SysAdmin 4, SQL 2
]

# (id, title, description, priority, estimated_duration_min, created_at)
DEMO_TASKS = [
    (1, "Speed up sales report SQL queries",
     "The monthly sales report takes too long to build", "high", 120,
     "2026-11-16 09:00:00"),
    (2, "Data export API",
     "Service that exports database records as JSON", "medium", 180,
     "2026-11-16 09:15:00"),
    (3, "Database migration script",
     "Move customer data to the new schema", "medium", 90,
     "2026-11-16 09:30:00"),
    (4, "Fix website contact form",
     "The contact form does not submit in Safari", "low", 60,
     "2026-11-16 10:00:00"),
    (5, "Set up VPN for branch office",
     "Connect the new office to the corporate network", "high", 240,
     "2026-11-16 10:30:00"),
    (6, "Network security audit",
     "Network infrastructure review with Python-automated checks", "high", 300,
     "2026-11-16 11:00:00"),
    (7, "Server OS updates",
     "Scheduled OS update on application servers", "low", 120,
     "2026-11-16 11:30:00"),
    (8, "Reporting web dashboard",
     "Page with charts built from database data", "medium", 150,
     "2026-11-16 12:00:00"),
]

# (task_id, skill_id, minimum_level)
DEMO_TASK_REQUIREMENTS = [
    (1, 1, 4), (1, 2, 3),   # Python >= 4, SQL >= 3
    (2, 1, 4), (2, 2, 3),   # Python >= 4, SQL >= 3
    (3, 1, 4), (3, 2, 2),   # Python >= 4, SQL >= 2
    (4, 3, 4),              # JavaScript >= 4
    (5, 4, 4), (5, 5, 3),   # Networking >= 4, SysAdmin >= 3
    (6, 4, 5), (6, 1, 4),   # Networking >= 5, Python >= 4  -> nobody qualifies
    (7, 5, 4),              # SysAdmin >= 4
    (8, 3, 3), (8, 2, 3),   # JavaScript >= 3, SQL >= 3
]


# --- Connection and initialisation ---

def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Insert demo data.

    INSERT OR IGNORE with fixed IDs: calling this again creates no duplicates
    and does not overwrite statuses changed during the demo.
    """
    with conn:
        conn.executemany("INSERT OR IGNORE INTO Skills (id, name) VALUES (?, ?)", DEMO_SKILLS)
        conn.executemany(
            "INSERT OR IGNORE INTO Employees (id, full_name, status) VALUES (?, ?, 'available')",
            DEMO_EMPLOYEES,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO EmployeeSkills (employee_id, skill_id, proficiency_level) "
            "VALUES (?, ?, ?)",
            DEMO_EMPLOYEE_SKILLS,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO Tasks "
            "(id, title, description, priority, estimated_duration, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            DEMO_TASKS,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO TaskRequirements (task_id, skill_id, minimum_level) "
            "VALUES (?, ?, ?)",
            DEMO_TASK_REQUIREMENTS,
        )


def init_database(
    db_path: str | Path = DEFAULT_DB_PATH, with_demo_data: bool = True
) -> sqlite3.Connection:
    """Create the schema if missing and optionally insert demo data."""
    conn = connect(db_path)
    create_schema(conn)
    if with_demo_data:
        seed_demo_data(conn)
    return conn


def reset_database(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Delete the database file and recreate it with demo data.

    All connections to this file must be closed before calling.
    """
    if str(db_path) != ":memory:":
        Path(db_path).unlink(missing_ok=True)
    return init_database(db_path)


# --- Loading entities ---

def _skills_by_employee(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    rows = conn.execute(
        "SELECT es.employee_id, s.name, es.proficiency_level "
        "FROM EmployeeSkills es JOIN Skills s ON s.id = es.skill_id "
        "ORDER BY es.employee_id, s.id"
    )
    result: dict[int, dict[str, int]] = {}
    for row in rows:
        result.setdefault(row["employee_id"], {})[row["name"]] = row["proficiency_level"]
    return result


def list_employees(conn: sqlite3.Connection) -> list[Employee]:
    skills = _skills_by_employee(conn)
    rows = conn.execute("SELECT id, full_name, status FROM Employees ORDER BY id")
    return [
        Employee(
            id=row["id"],
            full_name=row["full_name"],
            status=EmployeeStatus(row["status"]),
            skills=skills.get(row["id"], {}),
        )
        for row in rows
    ]


def get_employee(conn: sqlite3.Connection, employee_id: int) -> Employee | None:
    return next((e for e in list_employees(conn) if e.id == employee_id), None)


def list_skills(conn: sqlite3.Connection) -> list[str]:
    return [row["name"] for row in conn.execute("SELECT name FROM Skills ORDER BY id")]


def _task_requirements(conn: sqlite3.Connection, task_id: int) -> list[SkillRequirement]:
    rows = conn.execute(
        "SELECT s.name, tr.minimum_level "
        "FROM TaskRequirements tr JOIN Skills s ON s.id = tr.skill_id "
        "WHERE tr.task_id = ? ORDER BY s.id",
        (task_id,),
    )
    return [SkillRequirement(row["name"], row["minimum_level"]) for row in rows]


def _row_to_task(conn: sqlite3.Connection, row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=Priority(row["priority"]),
        estimated_duration=row["estimated_duration"],
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        requirements=_task_requirements(conn, row["id"]),
    )


def list_tasks(conn: sqlite3.Connection) -> list[Task]:
    rows = conn.execute("SELECT * FROM Tasks ORDER BY id").fetchall()
    return [_row_to_task(conn, row) for row in rows]


def get_task(conn: sqlite3.Connection, task_id: int) -> Task | None:
    row = conn.execute("SELECT * FROM Tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(conn, row) if row else None


def list_assignments(
    conn: sqlite3.Connection, only_active: bool = False
) -> list[AssignmentRecord]:
    query = (
        "SELECT a.id, a.task_id, t.title, a.employee_id, e.full_name, a.assigned_at, a.status "
        "FROM Assignments a "
        "JOIN Tasks t ON t.id = a.task_id "
        "JOIN Employees e ON e.id = a.employee_id "
    )
    if only_active:
        query += "WHERE a.status = 'active' "
    query += "ORDER BY a.id"
    return [
        AssignmentRecord(
            id=row["id"],
            task_id=row["task_id"],
            task_title=row["title"],
            employee_id=row["employee_id"],
            employee_name=row["full_name"],
            assigned_at=row["assigned_at"],
            status=AssignmentStatus(row["status"]),
        )
        for row in conn.execute(query)
    ]
