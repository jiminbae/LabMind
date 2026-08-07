import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from backend.db_init import PROJECT_ROOT
from backend.db_utils import (
    IntakeConflictError,
    ReagentValidationError,
    insert_reagent,
    list_reagents,
    query_by_cas,
)


class DatabaseUtilityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = PROJECT_ROOT / ".review" / "test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(dir=temporary_root)
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"
        self.base_reagent = {
            "name": "Water",
            "cas_number": "7732-18-5",
            "catalog_number": "WATER-1",
            "lot_number": "LOT-1",
            "manufacturer": "Example",
            "quantity": 2,
            "quantity_unit": "unit",
            "volume_ml": 2500,
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_confirmed_reagent_is_inserted_and_returns_id(self) -> None:
        reagent_id = insert_reagent(
            self.base_reagent,
            self.database_path,
            confirmed=True,
        )

        self.assertEqual(reagent_id, 1)
        rows = list_reagents(self.database_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], reagent_id)
        self.assertEqual(rows[0]["cas_number"], "7732-18-5")
        self.assertEqual(rows[0]["quantity"], 2)
        self.assertEqual(rows[0]["volume_ml"], 2500)

    def test_unconfirmed_reagent_is_rejected_without_creating_database(self) -> None:
        with self.assertRaisesRegex(
            ReagentValidationError,
            "confirmation is required",
        ):
            insert_reagent(self.base_reagent, self.database_path)

        self.assertFalse(self.database_path.exists())

    def test_invalid_cas_is_rejected_before_database_write(self) -> None:
        reagent = {**self.base_reagent, "cas_number": "7732-18-4"}

        with self.assertRaisesRegex(ReagentValidationError, "checksum failed"):
            insert_reagent(reagent, self.database_path, confirmed=True)

        self.assertFalse(self.database_path.exists())

    def test_negative_and_non_finite_quantities_are_rejected(self) -> None:
        for quantity in (-1, 1.5, "not-a-number", float("inf"), True):
            with self.subTest(quantity=quantity):
                reagent = {**self.base_reagent, "quantity": quantity}
                with self.assertRaisesRegex(
                    ReagentValidationError,
                    "non-negative whole number",
                ):
                    insert_reagent(
                        reagent,
                        self.database_path,
                        confirmed=True,
                    )

        self.assertFalse(self.database_path.exists())

    def test_negative_and_non_finite_volumes_are_rejected(self) -> None:
        for volume_ml in (-1, "not-a-number", float("inf"), True):
            with self.subTest(volume_ml=volume_ml):
                reagent = {**self.base_reagent, "volume_ml": volume_ml}
                with self.assertRaisesRegex(
                    ReagentValidationError,
                    "volume_ml must be a non-negative number",
                ):
                    insert_reagent(
                        reagent,
                        self.database_path,
                        confirmed=True,
                    )

        self.assertFalse(self.database_path.exists())

    def test_legacy_litre_amount_is_converted_to_count_and_volume(self) -> None:
        reagent = {
            **self.base_reagent,
            "quantity": 2.5,
            "quantity_unit": "L",
        }
        reagent.pop("volume_ml")

        insert_reagent(reagent, self.database_path, confirmed=True)
        stored = list_reagents(self.database_path)[0]

        self.assertEqual(stored["quantity"], 1)
        self.assertEqual(stored["quantity_unit"], "unit")
        self.assertEqual(stored["volume_ml"], 2500)

    def test_same_cas_can_store_multiple_lots_and_returns_newest_first(self) -> None:
        first_id = insert_reagent(
            self.base_reagent,
            self.database_path,
            confirmed=True,
        )
        second_id = insert_reagent(
            {**self.base_reagent, "lot_number": "LOT-2"},
            self.database_path,
            confirmed=True,
        )

        rows = query_by_cas(" 7732-18-5 ", self.database_path)

        self.assertEqual([row["id"] for row in rows], [second_id, first_id])
        self.assertEqual(
            [row["lot_number"] for row in rows],
            ["LOT-2", "LOT-1"],
        )

    def test_query_by_cas_rejects_invalid_value(self) -> None:
        with self.assertRaises(ReagentValidationError):
            query_by_cas("not-a-cas", self.database_path)

        self.assertFalse(self.database_path.exists())

    def test_json_fields_round_trip_as_lists(self) -> None:
        reagent = {
            **self.base_reagent,
            "chemical_tags": [" solvent ", "polar"],
            "hazard_labels": '["low-risk", "review"]',
        }

        insert_reagent(reagent, self.database_path, confirmed=True)
        row = list_reagents(self.database_path)[0]

        self.assertEqual(row["chemical_tags"], ["solvent", "polar"])
        self.assertEqual(row["hazard_labels"], ["low-risk", "review"])
        self.assertIs(row["manual_review"], True)

        with closing(sqlite3.connect(self.database_path)) as connection:
            stored = connection.execute(
                "SELECT chemical_tags, hazard_labels FROM reagents"
            ).fetchone()

        self.assertEqual(json.loads(stored[0]), ["solvent", "polar"])
        self.assertEqual(json.loads(stored[1]), ["low-risk", "review"])

    def test_invalid_json_list_is_rejected(self) -> None:
        reagent = {**self.base_reagent, "chemical_tags": "solvent"}

        with self.assertRaisesRegex(ReagentValidationError, "JSON array"):
            insert_reagent(reagent, self.database_path, confirmed=True)

        self.assertFalse(self.database_path.exists())

    def test_expiry_date_and_optional_defaults_are_normalized(self) -> None:
        reagent = {
            "name": "  Acetone  ",
            "cas_number": " 67-64-1 ",
            "expiry_date": date(2027, 7, 27),
        }

        insert_reagent(reagent, self.database_path, confirmed=True)
        row = list_reagents(self.database_path)[0]

        self.assertEqual(row["name"], "Acetone")
        self.assertEqual(row["cas_number"], "67-64-1")
        self.assertEqual(row["quantity"], 0)
        self.assertEqual(row["quantity_unit"], "unit")
        self.assertEqual(row["volume_ml"], 0)
        self.assertEqual(row["expiry_date"], "2027-07-27")
        self.assertEqual(row["chemical_tags"], [])
        self.assertEqual(row["hazard_labels"], [])

    def test_list_reagents_returns_all_rows_newest_first(self) -> None:
        first_id = insert_reagent(
            self.base_reagent,
            self.database_path,
            confirmed=True,
        )
        second_id = insert_reagent(
            {
                "name": "Acetone",
                "cas_number": "67-64-1",
                "lot_number": "ACE-1",
            },
            self.database_path,
            confirmed=True,
        )

        rows = list_reagents(self.database_path)

        self.assertEqual([row["id"] for row in rows], [second_id, first_id])
        self.assertEqual([row["name"] for row in rows], ["Acetone", "Water"])

    def test_receipt_key_makes_exact_retries_idempotent(self) -> None:
        reagent = {**self.base_reagent, "receipt_key": "camera:abc123"}

        first_id = insert_reagent(reagent, self.database_path, confirmed=True)
        second_id = insert_reagent(reagent, self.database_path, confirmed=True)

        self.assertEqual(second_id, first_id)
        self.assertEqual(len(list_reagents(self.database_path)), 1)

    def test_receipt_key_rejects_changed_replay(self) -> None:
        reagent = {**self.base_reagent, "receipt_key": "camera:abc123"}
        insert_reagent(reagent, self.database_path, confirmed=True)

        with self.assertRaises(IntakeConflictError):
            insert_reagent(
                {**reagent, "quantity": 3},
                self.database_path,
                confirmed=True,
            )

    def test_intake_id_becomes_an_idempotency_key(self) -> None:
        reagent = {**self.base_reagent, "intake_id": "RECEIPT-2026-001"}

        first_id = insert_reagent(reagent, self.database_path, confirmed=True)
        second_id = insert_reagent(reagent, self.database_path, confirmed=True)
        stored = list_reagents(self.database_path)[0]

        self.assertEqual(second_id, first_id)
        self.assertEqual(stored["intake_id"], "RECEIPT-2026-001")
        self.assertEqual(stored["receipt_key"], "intake:RECEIPT-2026-001")

    def test_optional_intake_metadata_and_ui_aliases_round_trip(self) -> None:
        reagent = {
            **self.base_reagent,
            "receipt_key": "camera:metadata",
            "pending_order": "PO-2026-1842",
            "match_score": 0.98,
            "image_signature": "a" * 64,
            "confidence": 0.92,
            "extraction_source": "vision-provider",
            "extraction_rationale": "Label fields were readable.",
            "classification_confidence": 0.94,
            "classification_source": "CAS cache",
            "classification_rationale": "Reviewed chemistry profile.",
        }

        insert_reagent(reagent, self.database_path, confirmed=True)
        stored = list_reagents(self.database_path)[0]

        self.assertEqual(stored["order_reference"], "PO-2026-1842")
        self.assertEqual(stored["match_score"], 0.98)
        self.assertEqual(stored["image_signature"], "a" * 64)
        self.assertEqual(stored["extraction_confidence"], 0.92)
        self.assertEqual(stored["classification_source"], "CAS cache")


if __name__ == "__main__":
    unittest.main()
