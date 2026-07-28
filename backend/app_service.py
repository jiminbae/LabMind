"""Adapter between the Streamlit intake payload and the inventory backend."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import pandas as pd

from .chemistry_catalog import smiles_for_cas
from .classification_cache import upsert_cas_classification
from .db_utils import list_reagents
from .intake_service import register_intake
from .order_matching import mark_order_received
from .safety_rules import determine_storage_location


INVENTORY_COLUMNS = (
    "Record ID",
    "Chemical name",
    "CAS number",
    "Manufacturer",
    "Batch number",
    "Specification",
    "Quantity",
    "Unit",
    "Expiry date",
    "Storage location",
    "SMILES",
    "Chemical labels",
    "Storage constraints",
    "Expiry state",
    "Status",
    "Order reference",
    "Classification source",
)


def _text(value: object, default: str = "Not recorded") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_text(value: object) -> str | None:
    normalized = _text(value, default="")
    return normalized or None


def _order_reference(value: object) -> str | None:
    reference = _optional_text(value)
    return None if reference in {None, "Not linked"} else reference


def payload_to_reagent_data(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map one reviewed UI payload to the validated database contract.

    The final location and the deterministic recommendation are stored
    separately.  That preserves a reviewer-approved override without changing
    the rule engine's original safety conclusion.
    """

    constraints = _list(payload.get("storage_constraints"))
    decision = determine_storage_location(constraints)
    cas_number = _text(payload.get("cas_number"), default="")
    return {
        "name": _text(payload.get("chemical_name"), default=""),
        "cas_number": cas_number,
        "catalog_number": _optional_text(payload.get("catalog_number")),
        "specification": _optional_text(payload.get("specification")),
        "lot_number": _optional_text(payload.get("batch_number")),
        "manufacturer": _optional_text(payload.get("manufacturer")),
        "quantity": payload.get("quantity", 0),
        "quantity_unit": _optional_text(payload.get("unit")) or "unit",
        "location": _optional_text(payload.get("storage_location"))
        or decision["location"],
        "expiry_date": _optional_text(payload.get("expiry_date")),
        "smiles": _optional_text(payload.get("smiles")) or smiles_for_cas(cas_number),
        "chemical_tags": _list(payload.get("chemical_labels")),
        "hazard_labels": constraints,
        "storage_suggestion": decision["location"],
        "storage_reason": _optional_text(payload.get("storage_rule"))
        or decision["rule"],
        "manual_review": not bool(payload.get("storage_reviewed")),
        "receipt_key": _optional_text(
            payload.get("receipt_key") or payload.get("intake_id")
        ),
        "image_signature": _optional_text(payload.get("image_signature")),
        "order_reference": _order_reference(payload.get("pending_order")),
        "match_score": payload.get("match_score"),
        "extraction_confidence": payload.get("confidence"),
        "extraction_source": _optional_text(payload.get("extraction_source")),
        "extraction_rationale": _optional_text(
            payload.get("extraction_rationale")
        ),
        "classification_confidence": payload.get("classification_confidence"),
        "classification_source": _optional_text(
            payload.get("classification_source")
        ),
        "classification_rationale": _optional_text(
            payload.get("classification_rationale")
        ),
    }


def register_reagent_payload(
    payload: Mapping[str, Any],
    *,
    reviewed: bool,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Commit a reviewed intake and cache its human-confirmed classification."""

    if not reviewed:
        raise ValueError("Registration requires reviewed information.")
    reagent_data = payload_to_reagent_data(payload)
    outcome = register_intake(reagent_data, db_path, confirmed=True)

    # A reviewer-approved label set is reusable only by the same normalized CAS.
    # This is deliberately best-effort: failure to update the cache must not
    # undo the physical intake record that was already committed transactionally.
    classification_warning: str | None = None
    if reagent_data["chemical_tags"] or reagent_data["hazard_labels"]:
        try:
            upsert_cas_classification(
                reagent_data["cas_number"],
                chemical_tags=reagent_data["chemical_tags"],
                hazard_labels=reagent_data["hazard_labels"],
                confidence=reagent_data["classification_confidence"],
                source=reagent_data["classification_source"] or "Reviewer confirmed",
                rationale=reagent_data["classification_rationale"],
                smiles=reagent_data["smiles"],
                reviewed=True,
                db_path=db_path,
            )
        except (RuntimeError, ValueError) as error:
            classification_warning = str(error)

    reagent_id = int(outcome["id"])
    order_reference = reagent_data["order_reference"]
    order_warning: str | None = None
    if order_reference:
        try:
            mark_order_received(order_reference, reagent_id, db_path)
        except ValueError as error:
            # The physical intake is already durable.  Do not misreport it as
            # failed merely because a stale/external order reference could not
            # be reconciled after the fact.
            order_warning = str(error)
    return {
        "record_id": f"LAB-{reagent_id:04d}",
        "database_id": reagent_id,
        "created": bool(outcome.get("created", True)),
        "prepared_at": outcome.get("created_at"),
        "classification_warning": classification_warning,
        "order_warning": order_warning,
        "payload": dict(payload),
    }


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _expiry_state(expiry_date: date | None, today: date) -> str:
    if expiry_date is None:
        return "Not recorded"
    if expiry_date < today:
        return "Expired"
    if expiry_date <= today + timedelta(days=30):
        return "Expiring soon"
    return "Current"


def _inventory_status(
    quantity: float,
    expiry_state: str,
    manual_review: bool,
) -> str:
    if expiry_state == "Expired":
        return "Expired"
    if quantity <= 0:
        return "Unavailable"
    if manual_review:
        return "Review required"
    return "Available"


def reagent_rows_to_inventory_frame(
    rows: Sequence[Mapping[str, Any]],
    *,
    today: date | None = None,
) -> pd.DataFrame:
    """Translate persisted rows into the stable UI/query dataframe contract."""

    effective_today = today or date.today()
    records: list[dict[str, Any]] = []
    for row in rows:
        quantity = float(row.get("quantity") or 0)
        expiry_date = _parse_date(row.get("expiry_date"))
        expiry_state = _expiry_state(expiry_date, effective_today)
        record_id = int(row["id"])
        labels = _list(row.get("chemical_tags"))
        constraints = _list(row.get("hazard_labels"))
        records.append(
            {
                "Record ID": f"LAB-{record_id:04d}",
                "Chemical name": _text(row.get("name")),
                "CAS number": _text(row.get("cas_number")),
                "Manufacturer": _text(row.get("manufacturer")),
                "Batch number": _text(row.get("lot_number")),
                "Specification": _text(row.get("specification")),
                "Quantity": quantity,
                "Unit": _text(row.get("quantity_unit"), default="unit"),
                "Expiry date": expiry_date.isoformat() if expiry_date else "Not recorded",
                "Storage location": _text(row.get("location")),
                "SMILES": _text(row.get("smiles"), default="Not available"),
                "Chemical labels": " · ".join(labels) or "Unclassified",
                "Storage constraints": " · ".join(constraints) or "Review required",
                "Expiry state": expiry_state,
                "Status": _inventory_status(
                    quantity,
                    expiry_state,
                    bool(row.get("manual_review")),
                ),
                "Order reference": _text(row.get("order_reference")),
                "Classification source": _text(row.get("classification_source")),
            }
        )
    return pd.DataFrame(records, columns=INVENTORY_COLUMNS)


def load_inventory_frame(
    *,
    today: date | None = None,
    db_path: str | None = None,
) -> pd.DataFrame:
    """Load actual registered reagent lots; an empty database is valid."""

    return reagent_rows_to_inventory_frame(
        list_reagents(db_path),
        today=today,
    )
