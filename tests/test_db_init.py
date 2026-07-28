import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db_init import (
    DATABASE_SCHEMA_VERSION,
    PROJECT_ROOT,
    get_schema_version,
    init_db,
    resolve_db_path,
)


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = PROJECT_ROOT / ".review" / "test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(dir=temporary_root)
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initialization_creates_current_durable_tables(self) -> None:
        initialized_path = init_db(self.database_path)

        self.assertEqual(initialized_path, self.database_path.resolve())
        self.assertTrue(initialized_path.is_file())

        with closing(sqlite3.connect(initialized_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    """
                )
            }

        self.assertTrue(
            {
                "reagents",
                "storage_rules",
                "schema_migrations",
                "cas_classification_cache",
                "pending_orders",
            }.issubset(tables)
        )

    def test_reagent_schema_contains_required_intake_fields(self) -> None:
        initialized_path = init_db(self.database_path)

        with closing(sqlite3.connect(initialized_path)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(reagents)")
            }

        self.assertTrue(
            {
                "name",
                "cas_number",
                "quantity",
                "quantity_unit",
                "expiry_date",
                "chemical_tags",
                "hazard_labels",
                "storage_suggestion",
                "storage_reason",
                "manual_review",
                "receipt_key",
                "intake_id",
                "order_reference",
                "image_signature",
                "extraction_confidence",
                "classification_confidence",
            }.issubset(columns)
        )

    def test_legacy_reagent_table_is_upgraded_without_losing_rows(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE reagents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cas_number TEXT NOT NULL,
                    catalog_number TEXT,
                    specification TEXT,
                    lot_number TEXT,
                    manufacturer TEXT,
                    quantity REAL NOT NULL DEFAULT 0,
                    quantity_unit TEXT NOT NULL DEFAULT 'unit',
                    location TEXT,
                    expiry_date DATE,
                    smiles TEXT,
                    chemical_tags TEXT NOT NULL DEFAULT '[]',
                    hazard_labels TEXT NOT NULL DEFAULT '[]',
                    storage_suggestion TEXT,
                    storage_reason TEXT,
                    manual_review INTEGER NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO reagents (name, cas_number, quantity, quantity_unit)
                VALUES (?, ?, ?, ?)
                """,
                ("Water", "7732-18-5", 1.0, "L"),
            )
            connection.commit()

        init_db(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(reagents)")
            }
            row = connection.execute(
                "SELECT name, cas_number, quantity FROM reagents WHERE id = 1"
            ).fetchone()

        self.assertTrue(
            {
                "receipt_key",
                "intake_id",
                "classification_rationale",
            }.issubset(columns)
        )
        self.assertEqual(row, ("Water", "7732-18-5", 1.0))
        self.assertEqual(get_schema_version(self.database_path), DATABASE_SCHEMA_VERSION)

    def test_initialization_is_repeatable_without_duplicate_rules(self) -> None:
        init_db(self.database_path)
        init_db(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            rule_count = connection.execute(
                "SELECT COUNT(*) FROM storage_rules"
            ).fetchone()[0]

        self.assertEqual(rule_count, 4)

    def test_same_cas_and_catalog_can_have_multiple_lots(self) -> None:
        initialized_path = init_db(self.database_path)

        with closing(sqlite3.connect(initialized_path)) as connection:
            connection.execute(
                """
                INSERT INTO reagents (
                    name, cas_number, catalog_number, lot_number, manufacturer
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("Water", "7732-18-5", "WATER-1", "LOT-1", "Example"),
            )
            connection.execute(
                """
                INSERT INTO reagents (
                    name, cas_number, catalog_number, lot_number, manufacturer
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("Water", "7732-18-5", "WATER-1", "LOT-2", "Example"),
            )

            row_count = connection.execute(
                "SELECT COUNT(*) FROM reagents WHERE cas_number = ?",
                ("7732-18-5",),
            ).fetchone()[0]

        self.assertEqual(row_count, 2)

    def test_negative_quantity_is_rejected(self) -> None:
        initialized_path = init_db(self.database_path)

        with closing(sqlite3.connect(initialized_path)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO reagents (name, cas_number, quantity)
                    VALUES (?, ?, ?)
                    """,
                    ("Water", "7732-18-5", -1),
                )

    def test_relative_database_path_is_project_relative(self) -> None:
        path = resolve_db_path("local-test.db")

        self.assertEqual(path, PROJECT_ROOT / "local-test.db")


if __name__ == "__main__":
    unittest.main()
