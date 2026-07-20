import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from backend.schemas import OCRResult


class FakeUpload:
    name = "label.png"

    @staticmethod
    def getbuffer() -> bytes:
        return b"\x89PNG\r\n\x1a\nmock-image-bytes"


class StreamlitIntegrationTests(unittest.TestCase):
    def test_uploaded_file_is_removed_after_backend_analysis(self) -> None:
        captured_path = None

        def fake_analyze_label(image_path):
            nonlocal captured_path
            captured_path = Path(image_path)
            self.assertTrue(captured_path.is_file())
            return OCRResult(catalog_number="TEST-1")

        with patch("app.analyze_label", side_effect=fake_analyze_label):
            result = app.analyze_uploaded_file(FakeUpload())

        self.assertEqual(result["catalog_number"], "TEST-1")
        self.assertIsNotNone(captured_path)
        self.assertFalse(captured_path.exists())

    def test_display_value_escapes_model_text(self) -> None:
        self.assertEqual(
            app.display_value("<script>alert(1)</script>"),
            "&lt;script&gt;alert(1)&lt;/script&gt;",
        )

    def test_uploaded_file_reaches_real_backend_in_mock_mode(self) -> None:
        with patch.dict(os.environ, {"LABMIND_VISION_MODE": "mock"}):
            result = app.analyze_uploaded_file(FakeUpload())

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["ocr"]["catalog_number"], "HS4323K")


if __name__ == "__main__":
    unittest.main()
