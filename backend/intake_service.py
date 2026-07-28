"""Application-facing adapter for a confirmed reagent intake.

The module translates the Streamlit/UI vocabulary into the durable storage
vocabulary.  It contains no image recognition or safety-placement logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .db_utils import ReagentValidationError, insert_reagent, list_reagents


class IntakeServiceError(ReagentValidationError):
    """Raised when an application payload cannot become a confirmed intake."""


def _first_value(data: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def _normalize_optional_order_reference(value: object) -> object:
    if isinstance(value, str) and value.strip().casefold() in {
        "not linked",
        "selection required",
    }:
        return None
    return value


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def map_intake_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Map current UI field names to :func:`db_utils.insert_reagent` fields."""

    if not isinstance(data, Mapping):
        raise IntakeServiceError("Intake data must be a mapping.")

    mapped = {
        "name": _first_value(data, "name", "chemical_name"),
        "cas_number": data.get("cas_number"),
        "catalog_number": data.get("catalog_number"),
        "specification": data.get("specification"),
        "lot_number": _first_value(data, "lot_number", "batch_number"),
        "manufacturer": data.get("manufacturer"),
        "quantity": data.get("quantity"),
        "quantity_unit": _first_value(data, "quantity_unit", "unit"),
        "location": data.get("location"),
        "expiry_date": data.get("expiry_date"),
        "smiles": data.get("smiles"),
        "chemical_tags": _first_value(data, "chemical_tags", "chemical_labels"),
        "hazard_labels": _first_value(data, "hazard_labels", "storage_constraints"),
        "storage_suggestion": _first_value(
            data, "storage_suggestion", "storage_location"
        ),
        "storage_reason": _first_value(data, "storage_reason", "storage_rule"),
        "receipt_key": data.get("receipt_key"),
        "intake_id": data.get("intake_id"),
        "order_reference": _normalize_optional_order_reference(
            _first_value(data, "order_reference", "pending_order")
        ),
        "match_score": data.get("match_score"),
        "image_signature": data.get("image_signature"),
        "extraction_confidence": _first_value(
            data, "extraction_confidence", "confidence"
        ),
        "extraction_source": data.get("extraction_source"),
        "extraction_rationale": data.get("extraction_rationale"),
        "classification_confidence": data.get("classification_confidence"),
        "classification_source": data.get("classification_source"),
        "classification_rationale": data.get("classification_rationale"),
    }

    if "manual_review" in data:
        mapped["manual_review"] = data["manual_review"]
    elif "storage_reviewed" in data:
        # UI means "review has happened" while the database flag means the
        # inverse: manual review remains required.
        mapped["manual_review"] = not bool(data["storage_reviewed"])

    # A byte-level image signature is a safe replay key for one exact upload.
    # Do not infer identity from chemical fields; separate physical lots may
    # legitimately share every label attribute.
    if (
        _is_empty(mapped["receipt_key"])
        and _is_empty(mapped["intake_id"])
        and not _is_empty(mapped["image_signature"])
    ):
        mapped["receipt_key"] = f"image:{mapped['image_signature']}"
    return mapped


def _find_existing_identity(
    mapped: Mapping[str, Any],
    db_path: str | Path | None,
) -> int | None:
    receipt_key = mapped.get("receipt_key")
    intake_id = mapped.get("intake_id")
    if receipt_key is None and intake_id is None:
        return None
    matches = [
        row
        for row in list_reagents(db_path)
        if row.get("receipt_key") == receipt_key
        or (intake_id is not None and row.get("intake_id") == intake_id)
    ]
    if len(matches) == 1:
        return int(matches[0]["id"])
    return None


def register_intake(
    data: Mapping[str, Any],
    db_path: str | Path | None = None,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Store one reviewed receipt and return its deterministic display code."""

    mapped = map_intake_payload(data)
    if confirmed is not True:
        # Preserve db_utils' no-write-before-review guarantee.  In particular,
        # avoid creating an empty local database merely to inspect an identity.
        insert_reagent(mapped, db_path, confirmed=confirmed)
        raise AssertionError("insert_reagent should have rejected unconfirmed intake")
    existing_id = _find_existing_identity(mapped, db_path)
    reagent_id = insert_reagent(mapped, db_path, confirmed=confirmed)
    stored = next(
        (row for row in list_reagents(db_path) if int(row["id"]) == reagent_id),
        None,
    )
    return {
        "id": reagent_id,
        "record_code": f"LAB-{reagent_id:04d}",
        "created": existing_id is None,
        "created_at": stored.get("created_at") if stored else None,
        "payload": mapped,
    }
