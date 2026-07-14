import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from backend.pipeline import analyze_label
from backend.schemas import ExpiryState, OCRResult, ResultStatus


TODAY = date(2026, 7, 10)


def successful_ocr(catalog_number: str, expiry_date: str | None) -> OCRResult:
    return OCRResult(
        catalog_number=catalog_number,
        lot_number="PIPELINE-LOT",
        expiry_date=expiry_date,
        brand="Test Brand",
        confidence=0.95,
        status=ResultStatus.SUCCESS,
    )


class PipelineTests(unittest.TestCase):
    def test_warning_item_returns_inventory_product_and_alternatives(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("HS4323K", "2026-07-25"),
            today=TODAY,
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertTrue(result.inventory.found)
        self.assertEqual(result.inventory.quantity, 8)
        self.assertEqual(result.expiry_warning.state, ExpiryState.WARNING)
        self.assertTrue(result.expiry_warning.should_alert)
        self.assertEqual(len(result.alternatives), 2)
        self.assertTrue(result.product.found)

    def test_expired_item_returns_alternatives(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("EP022363514", "2026-06-30"),
            today=TODAY,
        )

        self.assertEqual(result.expiry_warning.state, ExpiryState.EXPIRED)
        self.assertEqual(result.expiry_warning.days_remaining, -10)
        self.assertEqual(len(result.alternatives), 2)

    def test_out_of_stock_item_returns_alternatives(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("HS4325", "2027-09-30"),
            today=TODAY,
        )

        self.assertEqual(result.expiry_warning.state, ExpiryState.VALID)
        self.assertEqual(result.inventory.quantity, 0)
        self.assertEqual(len(result.alternatives), 2)

    def test_healthy_stock_does_not_return_unneeded_alternatives(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("BR780420", "2028-01-31"),
            today=TODAY,
        )

        self.assertEqual(result.expiry_warning.state, ExpiryState.VALID)
        self.assertGreater(result.inventory.quantity, 0)
        self.assertEqual(result.alternatives, [])

    def test_ocr_date_takes_precedence_and_reports_mismatch(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("HS4323K", "2026-07-20"),
            today=TODAY,
        )

        self.assertTrue(result.expiry_mismatch)
        self.assertEqual(result.image_expiry, "2026-07-20")
        self.assertEqual(result.inventory_expiry, "2026-07-25")
        self.assertEqual(result.expiry_warning.effective_expiry_date, "2026-07-20")

    def test_failed_ocr_short_circuits_pipeline(self) -> None:
        failed_ocr = OCRResult(
            status=ResultStatus.FAILED,
            error_message="simulated OCR failure",
        )
        result = analyze_label("unused.png", ocr_result=failed_ocr, today=TODAY)

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertEqual(result.error_message, "simulated OCR failure")
        self.assertIsNone(result.inventory)

    def test_success_without_catalog_number_becomes_failure(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=OCRResult(confidence=0.2),
            today=TODAY,
        )

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertIn("Catalog number", result.error_message)

    def test_result_is_json_serializable_for_streamlit(self) -> None:
        result = analyze_label(
            "unused.png",
            ocr_result=successful_ocr("HS4323K", "2026-07-25"),
            today=TODAY,
        )

        encoded = json.dumps(result.to_dict())
        self.assertIn('"catalog_number": "HS4323K"', encoded)
        self.assertIn('"state": "warning"', encoded)

    def test_mock_vision_runs_the_complete_pipeline(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.write(b"\x89PNG\r\n\x1a\nmock-image-bytes")
        handle.close()
        image_path = Path(handle.name)

        try:
            result = analyze_label(image_path, mode="mock", today=TODAY)
        finally:
            image_path.unlink(missing_ok=True)

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.ocr.catalog_number, "HS4323K")
        self.assertEqual(result.expiry_warning.state, ExpiryState.WARNING)
        self.assertEqual(len(result.alternatives), 2)


if __name__ == "__main__":
    unittest.main()
