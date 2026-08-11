import tempfile
import unittest
from pathlib import Path

from backend.classification_cache import (
    ClassificationCacheValidationError,
    get_cas_classification,
    upsert_cas_classification,
)
from backend.db_init import PROJECT_ROOT
from backend.db_utils import ReagentValidationError, insert_reagent, list_reagents
from backend.intake_service import register_intake


class DurableBackendServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = PROJECT_ROOT / ".review" / "test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(dir=temporary_root)
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"
        self.base_reagent = {
            "name": "Acetone",
            "cas_number": "67-64-1",
            "catalog_number": "A-001",
            "specification": "ACS grade",
            "lot_number": "LOT-42",
            "manufacturer": "Example Chemical",
            "quantity": 1,
            "quantity_unit": "unit",
            "volume_ml": 500,
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_cas_classification_cache_round_trips_and_replaces_profile(self) -> None:
        first = upsert_cas_classification(
            "67-64-1",
            chemical_tags=["Solvent", "Ketone"],
            hazard_labels=["Flammable"],
            confidence=0.93,
            source="chemist review",
            rationale="Reviewed against the SDS.",
            smiles="CC(=O)C",
            reviewed=True,
            db_path=self.database_path,
        )
        second = upsert_cas_classification(
            "67-64-1",
            chemical_tags=["Solvent"],
            hazard_labels=["Flammable", "Keep away from oxidizers"],
            confidence=0.98,
            source="updated review",
            reviewed=False,
            db_path=self.database_path,
        )

        stored = get_cas_classification(" 67-64-1 ", self.database_path)

        self.assertEqual(first["chemical_tags"], ["Solvent", "Ketone"])
        self.assertEqual(second["chemical_tags"], ["Solvent"])
        self.assertEqual(
            stored["hazard_labels"],
            ["Flammable", "Keep away from oxidizers"],
        )
        self.assertEqual(stored["source"], "updated review")
        self.assertFalse(stored["reviewed"])

    def test_cas_classification_cache_validates_cas_and_confidence(self) -> None:
        with self.assertRaises(ClassificationCacheValidationError):
            upsert_cas_classification(
                "67-64-2",
                confidence=0.5,
                db_path=self.database_path,
            )
        with self.assertRaises(ClassificationCacheValidationError):
            upsert_cas_classification(
                "67-64-1",
                confidence=1.1,
                db_path=self.database_path,
            )

        self.assertFalse(self.database_path.exists())

    def test_receipt_service_maps_ui_payload_and_image_key_is_idempotent(self) -> None:
        payload = {
            "chemical_name": "Acetone",
            "cas_number": "67-64-1",
            "specification": "ACS grade",
            "batch_number": "LOT-42",
            "manufacturer": "Example Chemical",
            "expiry_date": "2028-07-01",
            "quantity": 1,
            "volume_ml": 500,
            "confidence": 0.91,
            "pending_order": "PO-2026-1842",
            "chemical_labels": ["Solvent"],
            "storage_constraints": ["Flammable"],
            "classification_confidence": 0.94,
            "classification_source": "CAS cache",
            "classification_rationale": "Reviewed profile.",
            "storage_location": "Flammable Cabinet B",
            "storage_rule": "SR-04",
            "storage_reviewed": True,
            "image_signature": "f" * 64,
        }

        first = register_intake(payload, self.database_path, confirmed=True)
        retried = register_intake(payload, self.database_path, confirmed=True)
        stored = list_reagents(self.database_path)[0]

        self.assertTrue(first["created"])
        self.assertFalse(retried["created"])
        self.assertEqual(first["record_code"], "LAB-0001")
        self.assertEqual(retried["id"], first["id"])
        self.assertEqual(stored["receipt_key"], f"image:{'f' * 64}")
        self.assertFalse(stored["manual_review"])
        self.assertEqual(stored["order_reference"], "PO-2026-1842")

    def test_receipt_service_requires_confirmation_before_creating_database(self) -> None:
        with self.assertRaises(ReagentValidationError):
            register_intake(
                {"chemical_name": "Acetone", "cas_number": "67-64-1"},
                self.database_path,
            )
        self.assertFalse(self.database_path.exists())


if __name__ == "__main__":
    unittest.main()
