"""Initialize and safely upgrade the local LabMind SQLite database."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "schema.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "inventory.db"
DATABASE_SCHEMA_VERSION = 5


class DatabaseMigrationError(RuntimeError):
    """Raised when a local database cannot be upgraded without data loss."""


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve an explicit path, environment setting, or project default."""

    configured_path = db_path or os.environ.get("LABMIND_DB_PATH")
    if configured_path is None:
        return DEFAULT_DB_PATH

    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    column_definitions: dict[str, str],
) -> None:
    """Add known nullable/defaulted columns without rewriting stored records."""

    if not _table_exists(connection, table_name):
        raise DatabaseMigrationError(
            f"Expected local table {table_name!r} was not created by the schema."
        )

    existing_columns = _column_names(connection, table_name)
    for column_name, definition in column_definitions.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )
            existing_columns.add(column_name)


def _assert_no_duplicate_values(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
) -> None:
    duplicate = connection.execute(
        f"""
        SELECT {column_name}
        FROM {table_name}
        WHERE {column_name} IS NOT NULL
        GROUP BY {column_name}
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate is not None:
        raise DatabaseMigrationError(
            "Cannot create a unique index for "
            f"{table_name}.{column_name}: duplicate value {duplicate[0]!r} exists. "
            "Resolve the duplicate manually; no records were removed."
        )


def _ensure_unique_index(
    connection: sqlite3.Connection,
    *,
    index_name: str,
    table_name: str,
    column_name: str,
    where_not_null: bool = False,
) -> None:
    _assert_no_duplicate_values(
        connection,
        table_name=table_name,
        column_name=column_name,
    )
    predicate = f" WHERE {column_name} IS NOT NULL" if where_not_null else ""
    connection.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
        f"ON {table_name} ({column_name}){predicate}"
    )


REAGENT_INTAKE_COLUMNS = {
    "receipt_key": "TEXT",
    "intake_id": "TEXT",
    "order_reference": "TEXT",
    "match_score": (
        "REAL CHECK (match_score IS NULL OR "
        "(match_score >= 0 AND match_score <= 1))"
    ),
    "image_signature": "TEXT",
    "extraction_confidence": (
        "REAL CHECK (extraction_confidence IS NULL OR "
        "(extraction_confidence >= 0 AND extraction_confidence <= 1))"
    ),
    "extraction_source": "TEXT",
    "extraction_rationale": "TEXT",
    "classification_confidence": (
        "REAL CHECK (classification_confidence IS NULL OR "
        "(classification_confidence >= 0 AND classification_confidence <= 1))"
    ),
    "classification_source": "TEXT",
    "classification_rationale": "TEXT",
}

CLASSIFICATION_CACHE_COLUMNS = {
    "chemical_tags": "TEXT NOT NULL DEFAULT '[]'",
    "hazard_labels": "TEXT NOT NULL DEFAULT '[]'",
    "confidence": (
        "REAL CHECK (confidence IS NULL OR "
        "(confidence >= 0 AND confidence <= 1))"
    ),
    "source": "TEXT NOT NULL DEFAULT 'manual'",
    "rationale": "TEXT",
    "smiles": "TEXT",
    "reviewed": "INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1))",
    # SQLite cannot add a CURRENT_TIMESTAMP default to an existing table.
    # Nullable timestamps are safe for a hypothetical partial pre-release table;
    # all writes made by this version populate them explicitly.
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

PENDING_ORDER_COLUMNS = {
    "name": "TEXT NOT NULL DEFAULT ''",
    "cas_number": "TEXT",
    "catalog_number": "TEXT",
    "specification": "TEXT",
    "manufacturer": "TEXT",
    "quantity": "REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0)",
    "quantity_unit": "TEXT NOT NULL DEFAULT 'unit'",
    "status": (
        "TEXT NOT NULL DEFAULT 'pending' CHECK "
        "(status IN ('pending', 'matched', 'received', 'cancelled'))"
    ),
    "received_reagent_id": "INTEGER",
    "received_at": "DATETIME",
    "source": "TEXT",
    "raw_payload": "TEXT NOT NULL DEFAULT '{}'",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}


def _migrate_intake_metadata(connection: sqlite3.Connection) -> None:
    _ensure_columns(connection, "reagents", REAGENT_INTAKE_COLUMNS)
    _ensure_unique_index(
        connection,
        index_name="idx_reagents_receipt_key_unique",
        table_name="reagents",
        column_name="receipt_key",
        where_not_null=True,
    )
    _ensure_unique_index(
        connection,
        index_name="idx_reagents_intake_id_unique",
        table_name="reagents",
        column_name="intake_id",
        where_not_null=True,
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_reagents_order_reference "
        "ON reagents (order_reference)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_reagents_image_signature "
        "ON reagents (image_signature)"
    )


def _migrate_classification_cache(connection: sqlite3.Connection) -> None:
    _ensure_columns(
        connection,
        "cas_classification_cache",
        CLASSIFICATION_CACHE_COLUMNS,
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_classification_cache_updated_at "
        "ON cas_classification_cache (updated_at DESC)"
    )


def _migrate_pending_orders(connection: sqlite3.Connection) -> None:
    if "order_reference" not in _column_names(connection, "pending_orders"):
        raise DatabaseMigrationError(
            "The pending_orders table has no order_reference column and cannot "
            "be safely upgraded automatically."
        )

    _ensure_columns(connection, "pending_orders", PENDING_ORDER_COLUMNS)
    _ensure_unique_index(
        connection,
        index_name="idx_pending_orders_reference_unique",
        table_name="pending_orders",
        column_name="order_reference",
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pending_orders_status "
        "ON pending_orders (status, created_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pending_orders_cas_number "
        "ON pending_orders (cas_number)"
    )


def _migrate_quantity_and_volume(connection: sqlite3.Connection) -> None:
    """Split legacy amount values into container count and volume in millilitres."""

    for table_name in ("reagents", "pending_orders"):
        existing_columns = _column_names(connection, table_name)
        had_volume_column = "volume_ml" in existing_columns
        _ensure_columns(
            connection,
            table_name,
            {"volume_ml": "REAL NOT NULL DEFAULT 0 CHECK (volume_ml >= 0)"},
        )
        if had_volume_column:
            continue
        connection.execute(
            f"""
            UPDATE {table_name}
            SET
                volume_ml = CASE LOWER(TRIM(quantity_unit))
                    WHEN 'ml' THEN quantity
                    WHEN 'l' THEN quantity * 1000
                    ELSE 0
                END,
                quantity = CASE WHEN quantity > 0 THEN 1 ELSE 0 END,
                quantity_unit = 'unit'
            """
        )


MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (1, lambda connection: None),
    (2, _migrate_intake_metadata),
    (3, _migrate_classification_cache),
    (4, _migrate_pending_orders),
    (5, _migrate_quantity_and_volume),
)


def _apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied_versions = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations")
    }

    # Always run additive checks before recording an already-known version.  It
    # makes initialization self-healing for an interrupted local deployment.
    for version, migration in MIGRATIONS:
        migration(connection)
        if version not in applied_versions:
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )


def init_db(
    db_path: str | Path | None = None,
    *,
    schema_path: str | Path | None = None,
) -> Path:
    """Create or safely upgrade the local SQLite schema and return its path."""

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

    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        # WAL makes concurrent Streamlit reruns less likely to fail with a
        # transient read/write lock while preserving normal SQLite semantics.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(schema_sql)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _apply_migrations(connection)
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

    return resolved_db_path


def get_schema_version(db_path: str | Path | None = None) -> int:
    """Return the highest successfully recorded local schema migration."""

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path)) as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
    return int(row[0])


if __name__ == "__main__":
    initialized_path = init_db()
    print(f"Database initialized: {initialized_path}")
