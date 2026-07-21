import json
import unittest

from backend.schemas import (
    AnalysisResult,
    ExpiryState,
    ExpiryWarning,
    InventoryItem,
    OCRResult,
    ResultStatus,
)


class SchemaTests(unittest.TestCase):
    def test_success_result_is_json_serializable(self) -> None:
        result = AnalysisResult(
            status=ResultStatus.SUCCESS,
            ocr=OCRResult(
                catalog_number="HS4323K",
                lot_number="LOT-001",
                expiry_date="2026-07-25",
                confidence=0.94,
            ),
            inventory=InventoryItem(
                found=True,
                catalog_number="HS4323K",
                brand="Sigma-Aldrich",
                expiry_date="2026-07-25",
                quantity=8,
                location="Shelf A1",
            ),
            expiry_warning=ExpiryWarning(
                state=ExpiryState.WARNING,
                effective_expiry_date="2026-07-25",
                days_remaining=15,
                should_alert=True,
            ),
        )

        payload = result.to_dict()
        encoded = json.dumps(payload)

        self.assertIn('"status": "success"', encoded)
        self.assertEqual(payload["ocr"]["catalog_number"], "HS4323K")
        self.assertTrue(payload["expiry_warning"]["should_alert"])

    def test_failed_ocr_requires_an_error_message(self) -> None:
        with self.assertRaises(ValueError):
            OCRResult(status=ResultStatus.FAILED)

    def test_confidence_range_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            OCRResult(confidence=1.1)

    def test_inventory_quantity_cannot_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            InventoryItem(found=True, catalog_number="TEST", quantity=-1)


if __name__ == "__main__":
    unittest.main()
