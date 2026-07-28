"""Validated database operations for the current LabMind intake workflow."""

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
    "location",
    "expiry_date",
    "smiles",
    "chemical_tags",
    "hazard_labels",
    "storage_suggestion",
    "storage_reason",
    "manual_review",
)

JSON_LIST_COLUMNS = ("chemical_tags", "hazard_labels")


class ReagentValidationError(ValueError):
    """Raised when a reagent cannot safely be written to or queried from storage."""


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


def _quantity(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        raise ReagentValidationError("quantity must be a non-negative number.")

    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ReagentValidationError(
            "quantity must be a non-negative number."
        ) from exc

    if not math.isfinite(normalized) or normalized < 0:
        raise ReagentValidationError("quantity must be a non-negative number.")
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
        "quantity": _quantity(data.get("quantity")),
        "quantity_unit": quantity_unit or "unit",
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


def insert_reagent(
    data: Mapping[str, Any],
    db_path: str | Path | None = None,
    *,
    confirmed: bool = False,
) -> int:
    """Validate and insert one human-confirmed physical reagent lot."""

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

    with closing(sqlite3.connect(resolved_db_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"INSERT INTO reagents ({columns}) VALUES ({placeholders})",
                values,
            )
            reagent_id = cursor.lastrowid

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
