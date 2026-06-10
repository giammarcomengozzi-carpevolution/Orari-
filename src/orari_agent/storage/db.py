"""Connessione e schema SQLite per la memoria persistente del bot."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    target_week_start TEXT NOT NULL,
    target_week_end TEXT NOT NULL,
    interpreted_date TEXT,
    person TEXT,
    location TEXT,
    constraint_type TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_notes_week_status
ON notes(target_week_start, target_week_end, status);


CREATE TABLE IF NOT EXISTS operational_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    recurrence_rule TEXT,
    person TEXT,
    location TEXT,
    constraint_type TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT NOT NULL DEFAULT 'telegram',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_operational_memory_status_dates
ON operational_memory(status, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_operational_memory_recurrence
ON operational_memory(status, recurrence_rule);

CREATE TABLE IF NOT EXISTS generated_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    summary TEXT NOT NULL,
    warnings TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generated_schedules_week
ON generated_schedules(week_start, week_end);

CREATE TABLE IF NOT EXISTS wife_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wife_calendar_date
ON wife_calendar(date);

CREATE TABLE IF NOT EXISTS wife_calendar_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    image_path TEXT,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    warnings TEXT NOT NULL
);
"""


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Apre SQLite, crea la cartella se serve e inizializza lo schema."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialize(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    """Crea tutte le tabelle necessarie se non esistono."""

    connection.executescript(SCHEMA)
    connection.commit()
