import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.schemas import ResultStatus
from backend.vision_service import LabelExtraction, extract_label_info


class FakeResponses:
    def __init__(self, parsed=None, error=None) -> None:
        self.parsed = parsed
        self.error = error
        self.last_request = None

    def parse(self, **kwargs):
        self.last_request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, parsed=None, error=None) -> None:
        self.responses = FakeResponses(parsed=parsed, error=error)


class VisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.write(b"\x89PNG\r\n\x1a\nmock-image-bytes")
        handle.close()
        self.image_path = Path(handle.name)

    def tearDown(self) -> None:
        self.image_path.unlink(missing_ok=True)

    def test_mock_mode_returns_stable_success_result(self) -> None:
        result = extract_label_info(self.image_path, mode="mock")

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.catalog_number, "HS4323K")
        self.assertEqual(result.expiry_date, "2026-07-25")

    def test_live_mode_sends_image_and_parses_structured_result(self) -> None:
        client = FakeClient(
            parsed=LabelExtraction(
                catalog_number=" hs4323k ",
                lot_number="LOT-9",
                expiry_date="EXP 09/26",
                brand="Sigma-Aldrich",
                product_name=None,
                confidence=0.91,
            )
        )

        result = extract_label_info(
            self.image_path,
            mode="live",
            model="gpt-4o",
            client=client,
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.catalog_number, "HS4323K")
        self.assertEqual(result.expiry_date, "2026-09-30")
        request = client.responses.last_request
        self.assertEqual(request["model"], "gpt-4o")
        image_input = request["input"][1]["content"][1]
        self.assertEqual(image_input["type"], "input_image")
        self.assertTrue(image_input["image_url"].startswith("data:image/png;base64,"))

    def test_missing_catalog_number_is_a_failed_result(self) -> None:
        client = FakeClient(
            parsed=LabelExtraction(
                catalog_number=None,
                lot_number="LOT-9",
                expiry_date=None,
                brand=None,
                product_name=None,
                confidence=0.4,
            )
        )

        result = extract_label_info(self.image_path, mode="live", client=client)

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertIn("Catalog number", result.error_message)

    def test_api_exception_becomes_a_failed_result(self) -> None:
        client = FakeClient(error=TimeoutError("simulated"))

        result = extract_label_info(self.image_path, mode="live", client=client)

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertEqual(
            result.error_message, "Vision API request failed (TimeoutError)."
        )

    def test_invalid_file_inputs_do_not_raise(self) -> None:
        missing = extract_label_info("does-not-exist.png", mode="mock")
        unsupported = extract_label_info(__file__, mode="mock")

        self.assertEqual(missing.status, ResultStatus.FAILED)
        self.assertEqual(unsupported.status, ResultStatus.FAILED)

    def test_invalid_mode_does_not_raise(self) -> None:
        result = extract_label_info(self.image_path, mode="unexpected")

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertIn("mock", result.error_message)


if __name__ == "__main__":
    unittest.main()
