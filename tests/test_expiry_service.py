import unittest
from datetime import date

from backend.date_utils import normalize_expiry_date
from backend.expiry_service import check_expiry, resolve_effective_expiry
from backend.schemas import ExpiryState


class DateNormalizationTests(unittest.TestCase):
    def test_supported_date_formats(self) -> None:
        cases = {
            "2026-09-30": "2026-09-30",
            "09/30/2026": "2026-09-30",
            "09/30/26": "2026-09-30",
            "30-Sep-2026": "2026-09-30",
            "SEP 2026": "2026-09-30",
            "EXP 09/26": "2026-09-30",
            "2026-02": "2026-02-28",
        }

        for raw_date, expected in cases.items():
            with self.subTest(raw_date=raw_date):
                self.assertEqual(normalize_expiry_date(raw_date), expected)

    def test_invalid_date_returns_none(self) -> None:
        self.assertIsNone(normalize_expiry_date("not a date"))
        self.assertIsNone(normalize_expiry_date("2026-13"))
        self.assertIsNone(normalize_expiry_date(None))


class ExpiryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 7, 10)

    def test_expired_item(self) -> None:
        result = check_expiry("2026-07-09", today=self.today)
        self.assertEqual(result.state, ExpiryState.EXPIRED)
        self.assertEqual(result.days_remaining, -1)
        self.assertTrue(result.should_alert)

    def test_warning_boundary_is_inclusive(self) -> None:
        result = check_expiry("2026-08-09", today=self.today)
        self.assertEqual(result.state, ExpiryState.WARNING)
        self.assertEqual(result.days_remaining, 30)
        self.assertTrue(result.should_alert)

    def test_valid_item_outside_warning_window(self) -> None:
        result = check_expiry("2026-08-10", today=self.today)
        self.assertEqual(result.state, ExpiryState.VALID)
        self.assertEqual(result.days_remaining, 31)
        self.assertFalse(result.should_alert)

    def test_unknown_expiry_does_not_alert(self) -> None:
        result = check_expiry(None, today=self.today)
        self.assertEqual(result.state, ExpiryState.UNKNOWN)
        self.assertIsNone(result.days_remaining)
        self.assertFalse(result.should_alert)

    def test_image_expiry_takes_precedence_and_reports_mismatch(self) -> None:
        effective, mismatch = resolve_effective_expiry(
            "2026-07-25", "2026-09-30"
        )
        self.assertEqual(effective, "2026-07-25")
        self.assertTrue(mismatch)


if __name__ == "__main__":
    unittest.main()
