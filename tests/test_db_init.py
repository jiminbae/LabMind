import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db_init import PROJECT_ROOT, init_db, resolve_db_path


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = PROJECT_ROOT / ".review" / "test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(dir=temporary_root)
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initialization_creates_only_current_mvp_tables(self) -> None:
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

        self.assertEqual(tables, {"reagents", "storage_rules"})

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
            }.issubset(columns)
        )

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
