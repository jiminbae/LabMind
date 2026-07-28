"""CAS-keyed, human-reviewable chemistry classification cache."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from .cas_validator import validate_cas_details
from .db_init import init_db


class ClassificationCacheValidationError(ValueError):
    """Raised when a chemistry cache value is not safe to persist."""


def _text_list(value: Sequence[str], field_name: str) -> str:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ClassificationCacheValidationError(
            f"{field_name} must be a sequence of non-empty text values."
        )
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ClassificationCacheValidationError(
                f"{field_name} must contain only non-empty text values."
            )
        normalized.append(item.strip())
    return json.dumps(normalized, ensure_ascii=False)


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ClassificationCacheValidationError(f"{field_name} must be text.")
    normalized = value.strip()
    return normalized or None


def _confidence(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ClassificationCacheValidationError(
            "confidence must be a number from 0 to 1."
        )
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ClassificationCacheValidationError(
            "confidence must be a number from 0 to 1."
        ) from exc
    if not math.isfinite(normalized) or not 0 <= normalized <= 1:
        raise ClassificationCacheValidationError(
            "confidence must be a number from 0 to 1."
        )
    return normalized


def _reviewed(value: object) -> int:
    if value is True or value == 1:
        return 1
    if value is False or value == 0:
        return 0
    raise ClassificationCacheValidationError("reviewed must be true or false.")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for column in ("chemical_tags", "hazard_labels"):
        try:
            decoded = json.loads(result[column])
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Stored {column} value is not a valid JSON list."
            ) from exc
        if not isinstance(decoded, list):
            raise RuntimeError(f"Stored {column} value is not a JSON list.")
        result[column] = decoded
    result["reviewed"] = bool(result["reviewed"])
    return result


def _normalize_cas(cas_number: object) -> str:
    result = validate_cas_details(cas_number)
    if not result.is_valid or result.normalized_cas is None:
        raise ClassificationCacheValidationError(
            result.error_message or "CAS number is invalid."
        )
    return result.normalized_cas


def get_cas_classification(
    cas_number: object,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return a cached CAS classification, or ``None`` if it has not been reviewed."""

    normalized_cas = _normalize_cas(cas_number)
    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM cas_classification_cache
            WHERE cas_number = ?
            """,
            (normalized_cas,),
        ).fetchone()
    return _row_to_dict(row) if row is not None else None


def upsert_cas_classification(
    cas_number: object,
    *,
    chemical_tags: Sequence[str] = (),
    hazard_labels: Sequence[str] = (),
    confidence: object = None,
    source: object = None,
    rationale: object = None,
    smiles: object = None,
    reviewed: object = False,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create or replace the cache entry for one CAS number.

    The caller owns the safety review decision.  This helper stores labels and
    provenance only; it intentionally does not assign a physical location.
    """

    normalized_cas = _normalize_cas(cas_number)
    normalized_tags = _text_list(chemical_tags, "chemical_tags")
    normalized_hazards = _text_list(hazard_labels, "hazard_labels")
    normalized_source = _optional_text(source, "source") or "manual"
    normalized_rationale = _optional_text(rationale, "rationale")
    normalized_smiles = _optional_text(smiles, "smiles")
    normalized_confidence = _confidence(confidence)
    normalized_reviewed = _reviewed(reviewed)

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        with connection:
            connection.execute(
                """
                INSERT INTO cas_classification_cache (
                    cas_number,
                    chemical_tags,
                    hazard_labels,
                    confidence,
                    source,
                    rationale,
                    smiles,
                    reviewed,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(cas_number) DO UPDATE SET
                    chemical_tags = excluded.chemical_tags,
                    hazard_labels = excluded.hazard_labels,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    rationale = excluded.rationale,
                    smiles = excluded.smiles,
                    reviewed = excluded.reviewed,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    normalized_cas,
                    normalized_tags,
                    normalized_hazards,
                    normalized_confidence,
                    normalized_source,
                    normalized_rationale,
                    normalized_smiles,
                    normalized_reviewed,
                ),
            )
            row = connection.execute(
                "SELECT * FROM cas_classification_cache WHERE cas_number = ?",
                (normalized_cas,),
            ).fetchone()

    if row is None:
        raise RuntimeError("Classification cache write did not return a row.")
    return _row_to_dict(row)
