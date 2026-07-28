"""Initialize the local LabMind SQLite database."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "schema.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "inventory.db"


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve an explicit path, environment setting, or project default."""

    configured_path = db_path or os.environ.get("LABMIND_DB_PATH")
    if configured_path is None:
        return DEFAULT_DB_PATH

    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def init_db(
    db_path: str | Path | None = None,
    *,
    schema_path: str | Path | None = None,
) -> Path:
    """Create or update the local SQLite schema and return the database path."""

    resolved_db_path = resolve_db_path(db_path)
    resolved_schema_path = (
        Path(schema_path).expanduser().resolve()
        if schema_path is not None
        else DEFAULT_SCHEMA_PATH
    )

    if not resolved_schema_path.is_file():
        raise FileNotFoundError(f"Database schema not found: {resolved_schema_path}")

    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = resolved_schema_path.read_text(encoding="utf-8-sig")

    with closing(sqlite3.connect(resolved_db_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema_sql)

    return resolved_db_path


if __name__ == "__main__":
    initialized_path = init_db()
    print(f"Database initialized: {initialized_path}")
