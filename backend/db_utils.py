"""Validated SQLite operations for the LabMind intake workflow."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .cas_validator import validate_cas_details
from .db_init import init_db


REAGENT_COLUMNS = (
    "name",
    "cas_number",
    "catalog_number",
    "specification",
    "lot_number",
    "manufacturer",
    "quantity",
    "quantity_unit",
    "volume_ml",
    "location",
    "expiry_date",
    "smiles",
    "chemical_tags",
    "hazard_labels",
    "storage_suggestion",
    "storage_reason",
    "manual_review",
    "receipt_key",
    "intake_id",
    "order_reference",
    "match_score",
    "image_signature",
    "extraction_confidence",
    "extraction_source",
    "extraction_rationale",
    "classification_confidence",
    "classification_source",
    "classification_rationale",
)

JSON_LIST_COLUMNS = ("chemical_tags", "hazard_labels")


class ReagentValidationError(ValueError):
    """Raised when a reagent cannot safely be written to or queried from storage."""


class IntakeConflictError(ReagentValidationError):
    """Raised when one receipt identity is reused for different reagent data."""


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReagentValidationError(f"{field_name} is required and must be text.")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ReagentValidationError(f"{field_name} must be text when provided.")
    normalized = str(value).strip()
    return normalized or None


def _optional_alias(
    data: Mapping[str, Any],
    primary_name: str,
    alias_name: str,
) -> object:
    """Use a legacy/UI alias only when the canonical key is empty."""

    value = data.get(primary_name)
    if value is None or value == "":
        return data.get(alias_name)
    return value


def _quantity(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ReagentValidationError("quantity must be a non-negative whole number.")

    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ReagentValidationError(
            "quantity must be a non-negative whole number."
        ) from exc

    if not math.isfinite(normalized) or normalized < 0 or not normalized.is_integer():
        raise ReagentValidationError("quantity must be a non-negative whole number.")
    return int(normalized)


def _volume_ml(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        raise ReagentValidationError("volume_ml must be a non-negative number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ReagentValidationError(
            "volume_ml must be a non-negative number."
        ) from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise ReagentValidationError("volume_ml must be a non-negative number.")
    return normalized


def _quantity_and_volume(
    data: Mapping[str, Any], quantity_unit: str | None
) -> tuple[int, float]:
    """Accept the new count/volume fields and safely convert legacy mL/L amounts."""

    raw_volume = _optional_alias(data, "volume_ml", "volume")
    if raw_volume is not None and raw_volume != "":
        return _quantity(data.get("quantity")), _volume_ml(raw_volume)
    if quantity_unit and quantity_unit.casefold() in {"ml", "l"}:
        legacy_volume = _volume_ml(data.get("quantity"))
        multiplier = 1000 if quantity_unit.casefold() == "l" else 1
        return (1 if legacy_volume > 0 else 0), legacy_volume * multiplier
    return _quantity(data.get("quantity")), 0.0


def _confidence(value: object, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ReagentValidationError(f"{field_name} must be a number from 0 to 1.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ReagentValidationError(
            f"{field_name} must be a number from 0 to 1."
        ) from exc

    if not math.isfinite(normalized) or not 0 <= normalized <= 1:
        raise ReagentValidationError(f"{field_name} must be a number from 0 to 1.")
    return normalized


def _json_list(value: object, field_name: str) -> str:
    if value is None or value == "":
        items: object = []
    elif isinstance(value, str):
        try:
            items = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ReagentValidationError(
                f"{field_name} must be a JSON array or a sequence of text values."
            ) from exc
    else:
        items = value

    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ReagentValidationError(
            f"{field_name} must be a JSON array or a sequence of text values."
        )

    normalized_items: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ReagentValidationError(
                f"{field_name} may contain only non-empty text values."
            )
        normalized_items.append(item.strip())

    return json.dumps(normalized_items, ensure_ascii=False)


def _expiry_date(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ReagentValidationError("expiry_date must use YYYY-MM-DD format.")

    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as exc:
        raise ReagentValidationError(
            "expiry_date must use YYYY-MM-DD format."
        ) from exc


def _manual_review(value: object) -> int:
    if value is None:
        return 1
    if value is True or value == 1:
        return 1
    if value is False or value == 0:
        return 0
    raise ReagentValidationError("manual_review must be true or false.")


def _normalize_reagent(data: Mapping[str, Any]) -> dict[str, Any]:
    name = _required_text(data.get("name"), "name")

    cas_result = validate_cas_details(data.get("cas_number"))
    if not cas_result.is_valid or cas_result.normalized_cas is None:
        message = cas_result.error_message or "CAS number is invalid."
        raise ReagentValidationError(message)

    quantity_unit = _optional_text(data.get("quantity_unit"), "quantity_unit")
    quantity, volume_ml = _quantity_and_volume(data, quantity_unit)
    receipt_key = _optional_text(data.get("receipt_key"), "receipt_key")
    intake_id = _optional_text(data.get("intake_id"), "intake_id")
    # An upstream intake identifier is itself a valid idempotency key.  Keep
    # its original value too so operators can trace it back to the source.
    if receipt_key is None and intake_id is not None:
        receipt_key = f"intake:{intake_id}"

    extraction_confidence = _confidence(
        _optional_alias(data, "extraction_confidence", "confidence"),
        "extraction_confidence",
    )

    normalized: dict[str, Any] = {
        "name": name,
        "cas_number": cas_result.normalized_cas,
        "catalog_number": _optional_text(
            data.get("catalog_number"), "catalog_number"
        ),
        "specification": _optional_text(
            data.get("specification"), "specification"
        ),
        "lot_number": _optional_text(data.get("lot_number"), "lot_number"),
        "manufacturer": _optional_text(
            data.get("manufacturer"), "manufacturer"
        ),
        "quantity": quantity,
        "quantity_unit": "unit",
        "volume_ml": volume_ml,
        "location": _optional_text(data.get("location"), "location"),
        "expiry_date": _expiry_date(data.get("expiry_date")),
        "smiles": _optional_text(data.get("smiles"), "smiles"),
        "chemical_tags": _json_list(
            data.get("chemical_tags"), "chemical_tags"
        ),
        "hazard_labels": _json_list(
            data.get("hazard_labels"), "hazard_labels"
        ),
        "storage_suggestion": _optional_text(
            data.get("storage_suggestion"), "storage_suggestion"
        ),
        "storage_reason": _optional_text(
            data.get("storage_reason"), "storage_reason"
        ),
        "manual_review": _manual_review(data.get("manual_review")),
        "receipt_key": receipt_key,
        "intake_id": intake_id,
        "order_reference": _optional_text(
            _optional_alias(data, "order_reference", "pending_order"),
            "order_reference",
        ),
        "match_score": _confidence(data.get("match_score"), "match_score"),
        "image_signature": _optional_text(
            data.get("image_signature"), "image_signature"
        ),
        "extraction_confidence": extraction_confidence,
        "extraction_source": _optional_text(
            data.get("extraction_source"), "extraction_source"
        ),
        "extraction_rationale": _optional_text(
            data.get("extraction_rationale"), "extraction_rationale"
        ),
        "classification_confidence": _confidence(
            data.get("classification_confidence"),
            "classification_confidence",
        ),
        "classification_source": _optional_text(
            data.get("classification_source"), "classification_source"
        ),
        "classification_rationale": _optional_text(
            data.get("classification_rationale"), "classification_rationale"
        ),
    }
    return normalized


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for column in JSON_LIST_COLUMNS:
        try:
            decoded = json.loads(result[column])
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Stored {column} value is not valid JSON."
            ) from exc
        if not isinstance(decoded, list):
            raise RuntimeError(f"Stored {column} value is not a JSON array.")
        result[column] = decoded
    result["manual_review"] = bool(result["manual_review"])
    return result


def _identity_rows(
    connection: sqlite3.Connection,
    normalized: Mapping[str, Any],
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if normalized["receipt_key"] is not None:
        clauses.append("receipt_key = ?")
        parameters.append(normalized["receipt_key"])
    if normalized["intake_id"] is not None:
        clauses.append("intake_id = ?")
        parameters.append(normalized["intake_id"])
    if not clauses:
        return []
    return connection.execute(
        "SELECT * FROM reagents WHERE " + " OR ".join(clauses),
        parameters,
    ).fetchall()


def _stored_payload_matches(
    row: sqlite3.Row,
    normalized: Mapping[str, Any],
) -> bool:
    return all(row[column] == normalized[column] for column in REAGENT_COLUMNS)


def _return_existing_or_raise(
    rows: Sequence[sqlite3.Row],
    normalized: Mapping[str, Any],
) -> int | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise IntakeConflictError(
            "receipt_key and intake_id resolve to different stored reagents."
        )
    stored = rows[0]
    if _stored_payload_matches(stored, normalized):
        return int(stored["id"])
    raise IntakeConflictError(
        "A reagent already exists for this receipt_key or intake_id, but its "
        "stored details differ. Review the original intake instead of creating "
        "a duplicate."
    )


def insert_reagent(
    data: Mapping[str, Any],
    db_path: str | Path | None = None,
    *,
    confirmed: bool = False,
) -> int:
    """Validate and insert one human-confirmed physical reagent lot.

    Legacy callers may omit an intake identity and receive the historical
    append-only behavior.  New callers should send ``receipt_key`` or
    ``intake_id``; replaying the exact same confirmed intake then returns the
    original record ID without creating another physical lot.
    """

    if confirmed is not True:
        raise ReagentValidationError(
            "User confirmation is required before inserting a reagent."
        )
    if not isinstance(data, Mapping):
        raise ReagentValidationError("Reagent data must be a mapping.")

    normalized = _normalize_reagent(data)
    resolved_db_path = init_db(db_path)
    placeholders = ", ".join("?" for _ in REAGENT_COLUMNS)
    columns = ", ".join(REAGENT_COLUMNS)
    values = tuple(normalized[column] for column in REAGENT_COLUMNS)

    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_id = _return_existing_or_raise(
                _identity_rows(connection, normalized), normalized
            )
            if existing_id is not None:
                connection.commit()
                return existing_id

            cursor = connection.execute(
                f"INSERT INTO reagents ({columns}) VALUES ({placeholders})",
                values,
            )
            reagent_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            # A concurrent writer may have committed the same receipt after our
            # initial lookup.  Re-check it once so idempotent retries stay safe.
            if normalized["receipt_key"] is not None or normalized["intake_id"] is not None:
                with closing(sqlite3.connect(resolved_db_path, timeout=10)) as retry:
                    retry.row_factory = sqlite3.Row
                    existing_id = _return_existing_or_raise(
                        _identity_rows(retry, normalized), normalized
                    )
                    if existing_id is not None:
                        return existing_id
            raise ReagentValidationError(
                "Reagent could not be inserted because a database constraint failed."
            ) from exc
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

    if reagent_id is None:
        raise RuntimeError("Database did not return the inserted reagent ID.")
    return int(reagent_id)


def query_by_cas(
    cas: object,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return all reagent lots for one valid CAS number, newest first."""

    cas_result = validate_cas_details(cas)
    if not cas_result.is_valid or cas_result.normalized_cas is None:
        message = cas_result.error_message or "CAS number is invalid."
        raise ReagentValidationError(message)

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
            FROM reagents
            WHERE cas_number = ?
            ORDER BY created_at DESC, id DESC
            """,
            (cas_result.normalized_cas,),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def list_reagents(
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return all stored reagent lots, newest first."""

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
            FROM reagents
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [_row_to_dict(row) for row in rows]
