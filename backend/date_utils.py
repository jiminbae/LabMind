"""Date normalization helpers for OCR and inventory values."""

from __future__ import annotations

import calendar
import re
from datetime import datetime


_PREFIX_PATTERN = re.compile(
    r"^(?:EXP(?:IRY|IRATION)?(?:\s+DATE)?|USE\s+BY)\s*[:.-]?\s*",
    re.IGNORECASE,
)


def _last_day(year: int, month: int) -> str | None:
    try:
        day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (calendar.IllegalMonthError, ValueError):
        return None


def normalize_expiry_date(raw_date: str | None) -> str | None:
    """Return an ISO expiry date or ``None`` when the value is unusable.

    Month-only expiry values are interpreted as valid through the final day of
    that month, which matches common product-expiry conventions.
    """

    if raw_date is None:
        return None

    value = _PREFIX_PATTERN.sub("", str(raw_date).strip())
    value = re.sub(r"\s+", " ", value)
    if not value:
        return None

    for date_format in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    year_month = re.fullmatch(r"(\d{4})-(\d{1,2})", value)
    if year_month:
        return _last_day(int(year_month.group(1)), int(year_month.group(2)))

    numeric_month_year = re.fullmatch(r"(\d{1,2})/(\d{2}|\d{4})", value)
    if numeric_month_year:
        month = int(numeric_month_year.group(1))
        raw_year = numeric_month_year.group(2)
        year = int(raw_year) + 2000 if len(raw_year) == 2 else int(raw_year)
        return _last_day(year, month)

    for month_format in ("%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(value.title(), month_format)
            return _last_day(parsed.year, parsed.month)
        except ValueError:
            continue

    return None
