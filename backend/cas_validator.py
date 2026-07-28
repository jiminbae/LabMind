"""Validate Chemical Abstracts Service (CAS) Registry Numbers."""

from __future__ import annotations

import re
from dataclasses import dataclass


CAS_PATTERN = re.compile(
    r"^(?P<prefix>\d{2,7})-(?P<middle>\d{2})-(?P<check_digit>\d)$"
)


@dataclass(frozen=True, slots=True)
class CASValidationResult:
    """Detailed CAS validation result for API and UI consumers."""

    normalized_cas: str | None
    is_valid: bool
    error_message: str | None = None


def calculate_check_digit(body: str) -> int:
    """Calculate the CAS check digit from the digits before the final digit."""

    if not body or not body.isdigit():
        raise ValueError("CAS body must contain digits only.")

    weighted_sum = sum(
        int(character) * weight
        for weight, character in enumerate(reversed(body), start=1)
    )
    return weighted_sum % 10


def validate_cas_details(cas: object) -> CASValidationResult:
    """Validate CAS formatting and checksum without verifying registry identity."""

    if not isinstance(cas, str):
        return CASValidationResult(
            normalized_cas=None,
            is_valid=False,
            error_message="CAS number must be text.",
        )

    normalized = cas.strip()
    if not normalized:
        return CASValidationResult(
            normalized_cas=None,
            is_valid=False,
            error_message="CAS number is required.",
        )

    match = CAS_PATTERN.fullmatch(normalized)
    if match is None:
        return CASValidationResult(
            normalized_cas=normalized,
            is_valid=False,
            error_message=(
                "CAS number must use the format 2-7 digits, 2 digits, "
                "and 1 check digit (for example, 7732-18-5)."
            ),
        )

    body = f"{match.group('prefix')}{match.group('middle')}"
    expected = calculate_check_digit(body)
    actual = int(match.group("check_digit"))
    if actual != expected:
        return CASValidationResult(
            normalized_cas=normalized,
            is_valid=False,
            error_message=(
                f"CAS checksum failed: expected final digit {expected}, "
                f"received {actual}."
            ),
        )

    return CASValidationResult(normalized_cas=normalized, is_valid=True)


def validate_cas(cas: object) -> bool:
    """Return whether a CAS number has valid formatting and checksum."""

    return validate_cas_details(cas).is_valid


def is_valid_cas(cas: object) -> bool:
    """Backward-compatible alias for ``validate_cas``."""

    return validate_cas(cas)
