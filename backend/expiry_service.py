"""Expiry-date selection and warning logic."""

from __future__ import annotations

from datetime import date, datetime

from .date_utils import normalize_expiry_date
from .schemas import ExpiryState, ExpiryWarning


def _as_date(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


def resolve_effective_expiry(
    image_expiry: str | None,
    inventory_expiry: str | None,
) -> tuple[str | None, bool]:
    """Prefer the photographed label and report a database mismatch."""

    normalized_image = normalize_expiry_date(image_expiry)
    normalized_inventory = normalize_expiry_date(inventory_expiry)
    effective_expiry = normalized_image or normalized_inventory
    mismatch = bool(
        normalized_image
        and normalized_inventory
        and normalized_image != normalized_inventory
    )
    return effective_expiry, mismatch


def check_expiry(
    expiry_date: str | None,
    warning_days: int = 30,
    today: date | datetime | None = None,
) -> ExpiryWarning:
    """Classify an expiry date relative to ``today``."""

    if warning_days < 0:
        raise ValueError("warning_days cannot be negative")

    normalized = normalize_expiry_date(expiry_date)
    if normalized is None:
        return ExpiryWarning(
            state=ExpiryState.UNKNOWN,
            warning_days=warning_days,
            should_alert=False,
        )

    expiry = datetime.strptime(normalized, "%Y-%m-%d").date()
    days_remaining = (expiry - _as_date(today)).days

    if days_remaining < 0:
        state = ExpiryState.EXPIRED
        should_alert = True
    elif days_remaining <= warning_days:
        state = ExpiryState.WARNING
        should_alert = True
    else:
        state = ExpiryState.VALID
        should_alert = False

    return ExpiryWarning(
        state=state,
        effective_expiry_date=normalized,
        days_remaining=days_remaining,
        warning_days=warning_days,
        should_alert=should_alert,
    )
