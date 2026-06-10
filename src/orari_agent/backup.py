"""Creazione backup ZIP dei dati persistenti del bot."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupInfo:
    database_path: Path
    notes_count: int
    memories_count: int
    wife_calendar_entries_count: int
    latest_backup: Path | None


def create_backup(
    *,
    database_path: str | Path,
    data_dir: str | Path = "data",
    backup_dir: str | Path | None = None,
) -> Path:
    """Crea uno ZIP con database, import calendario moglie e metadata."""

    db_path = Path(database_path)
    root_data_dir = Path(data_dir)
    target_dir = (
        Path(backup_dir) if backup_dir is not None else root_data_dir / "backups"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = target_dir / f"backup_{timestamp}.zip"

    info = collect_backup_info(db_path, target_dir)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database_path": str(db_path),
        "data_dir": str(root_data_dir),
        "notes_count": info.notes_count,
        "memories_count": info.memories_count,
        "wife_calendar_entries_count": info.wife_calendar_entries_count,
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if db_path.exists():
            archive.write(db_path, arcname=f"data/{db_path.name}")
        imports_dir = root_data_dir / "imports"
        if imports_dir.exists():
            for file_path in sorted(
                path for path in imports_dir.rglob("*") if path.is_file()
            ):
                archive.write(
                    file_path, arcname=str(file_path.relative_to(root_data_dir.parent))
                )
        archive.writestr(
            "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2)
        )
    return zip_path


def collect_backup_info(
    database_path: str | Path,
    backup_dir: str | Path | None = None,
) -> BackupInfo:
    """Raccoglie conteggi rapidi per /backup_info senza modificare i dati."""

    db_path = Path(database_path)
    notes_count = memories_count = wife_count = 0
    if db_path.exists():
        connection = sqlite3.connect(db_path)
        try:
            notes_count = _count_table(connection, "notes")
            memories_count = _count_table(connection, "operational_memory")
            wife_count = _count_table(connection, "wife_calendar")
        finally:
            connection.close()

    latest_backup = None
    if backup_dir is not None:
        backups = sorted(Path(backup_dir).glob("backup_*.zip"))
        latest_backup = backups[-1] if backups else None
    return BackupInfo(db_path, notes_count, memories_count, wife_count, latest_backup)


def _count_table(connection: sqlite3.Connection, table_name: str) -> int:
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0
