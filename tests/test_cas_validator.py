import unittest

from backend.cas_validator import (
    calculate_check_digit,
    is_valid_cas,
    validate_cas,
    validate_cas_details,
)


class CASValidatorTests(unittest.TestCase):
    def test_known_valid_cas_numbers_pass(self) -> None:
        for cas_number in ("7732-18-5", "67-64-1", "75-09-2", "12345-67-4"):
            with self.subTest(cas_number=cas_number):
                self.assertTrue(validate_cas(cas_number))

    def test_invalid_checksums_fail(self) -> None:
        for cas_number in ("7732-18-4", "67-64-2", "12345-67-8"):
            with self.subTest(cas_number=cas_number):
                result = validate_cas_details(cas_number)
                self.assertFalse(result.is_valid)
                self.assertIn("checksum failed", result.error_message or "")

    def test_malformed_values_fail_without_raising(self) -> None:
        malformed_values = (
            None,
            7732185,
            "",
            "7732185",
            "7732--18-5",
            "77-3218-5",
            "A732-18-5",
        )

        for value in malformed_values:
            with self.subTest(value=value):
                self.assertFalse(validate_cas(value))

    def test_outer_whitespace_is_normalized(self) -> None:
        result = validate_cas_details("  7732-18-5  ")

        self.assertTrue(result.is_valid)
        self.assertEqual(result.normalized_cas, "7732-18-5")

    def test_compatibility_alias_matches_primary_function(self) -> None:
        self.assertEqual(is_valid_cas("75-09-2"), validate_cas("75-09-2"))

    def test_check_digit_calculation_rejects_non_digits(self) -> None:
        self.assertEqual(calculate_check_digit("773218"), 5)

        with self.assertRaises(ValueError):
            calculate_check_digit("77-3218")


if __name__ == "__main__":
    unittest.main()
