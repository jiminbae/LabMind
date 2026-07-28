"""Deterministic pending-order storage and receipt matching.

This module deliberately uses exact, explainable comparisons.  It can rank
orders for a human to select, but it never marks an order received on its own.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from .cas_validator import validate_cas_details
from .db_init import init_db


PENDING_ORDER_STATUSES = frozenset({"pending", "matched", "received", "cancelled"})


class PendingOrderValidationError(ValueError):
    """Raised when pending-order data cannot safely be stored or matched."""


class PendingOrderConflictError(PendingOrderValidationError):
    """Raised when an imported order would overwrite a finalized receipt."""


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PendingOrderValidationError(
            f"{field_name} is required and must be text."
        )
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise PendingOrderValidationError(f"{field_name} must be text.")
    normalized = str(value).strip()
    return normalized or None


def _first_value(data: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def _quantity(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        raise PendingOrderValidationError(
            "quantity must be a non-negative finite number."
        )
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise PendingOrderValidationError(
            "quantity must be a non-negative finite number."
        ) from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise PendingOrderValidationError(
            "quantity must be a non-negative finite number."
        )
    return normalized


def _optional_cas(value: object) -> str | None:
    if value is None or value == "":
        return None
    result = validate_cas_details(value)
    if not result.is_valid or result.normalized_cas is None:
        raise PendingOrderValidationError(
            result.error_message or "CAS number is invalid."
        )
    return result.normalized_cas


def _status(value: object) -> str:
    normalized = _optional_text(value, "status") or "pending"
    normalized = normalized.casefold()
    if normalized not in PENDING_ORDER_STATUSES:
        allowed = ", ".join(sorted(PENDING_ORDER_STATUSES))
        raise PendingOrderValidationError(f"status must be one of: {allowed}.")
    if normalized == "received":
        raise PendingOrderValidationError(
            "Use mark_order_received after a confirmed reagent insertion."
        )
    return normalized


def _json_payload(data: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(data),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise PendingOrderValidationError(
            "Order payload cannot be serialized for the local audit trail."
        ) from exc


def _normalize_order(
    data: Mapping[str, Any],
    *,
    source: object = None,
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise PendingOrderValidationError("Pending order data must be a mapping.")

    order_reference = _required_text(
        _first_value(data, "order_reference", "order_id"),
        "order_reference",
    )
    name = _required_text(
        _first_value(data, "name", "chemical_name"),
        "name",
    )
    quantity_unit = _optional_text(
        _first_value(data, "quantity_unit", "unit"),
        "quantity_unit",
    )
    return {
        "order_reference": order_reference,
        "name": name,
        "cas_number": _optional_cas(data.get("cas_number")),
        "catalog_number": _optional_text(
            data.get("catalog_number"), "catalog_number"
        ),
        "specification": _optional_text(
            data.get("specification"), "specification"
        ),
        "manufacturer": _optional_text(data.get("manufacturer"), "manufacturer"),
        "quantity": _quantity(data.get("quantity")),
        "quantity_unit": quantity_unit or "unit",
        "status": _status(data.get("status")),
        "source": _optional_text(
            source if source is not None else data.get("source"),
            "source",
        ),
        "raw_payload": _json_payload(data),
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    try:
        result["raw_payload"] = json.loads(result["raw_payload"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored pending-order payload is not valid JSON.") from exc
    return result


def _order_fields_match(existing: sqlite3.Row, incoming: Mapping[str, Any]) -> bool:
    columns = (
        "order_reference",
        "name",
        "cas_number",
        "catalog_number",
        "specification",
        "manufacturer",
        "quantity",
        "quantity_unit",
        "status",
        "source",
        "raw_payload",
    )
    return all(existing[column] == incoming[column] for column in columns)


def _upsert_pending_order(
    connection: sqlite3.Connection,
    incoming: Mapping[str, Any],
) -> tuple[sqlite3.Row, bool]:
    existing = connection.execute(
        "SELECT * FROM pending_orders WHERE order_reference = ?",
        (incoming["order_reference"],),
    ).fetchone()
    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO pending_orders (
                order_reference,
                name,
                cas_number,
                catalog_number,
                specification,
                manufacturer,
                quantity,
                quantity_unit,
                status,
                source,
                raw_payload,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                incoming["order_reference"],
                incoming["name"],
                incoming["cas_number"],
                incoming["catalog_number"],
                incoming["specification"],
                incoming["manufacturer"],
                incoming["quantity"],
                incoming["quantity_unit"],
                incoming["status"],
                incoming["source"],
                incoming["raw_payload"],
            ),
        )
        row = connection.execute(
            "SELECT * FROM pending_orders WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pending-order insert did not return a row.")
        return row, True

    if existing["status"] == "received":
        if _order_fields_match(existing, incoming):
            return existing, False
        raise PendingOrderConflictError(
            "A received order cannot be overwritten by an import. Use a new "
            "order reference or reconcile the receipt manually."
        )
    if existing["status"] == "cancelled":
        if _order_fields_match(existing, incoming):
            return existing, False
        raise PendingOrderConflictError(
            "A cancelled order cannot be reopened by an import without manual review."
        )
    if _order_fields_match(existing, incoming):
        return existing, False

    connection.execute(
        """
        UPDATE pending_orders
        SET
            name = ?,
            cas_number = ?,
            catalog_number = ?,
            specification = ?,
            manufacturer = ?,
            quantity = ?,
            quantity_unit = ?,
            status = ?,
            source = ?,
            raw_payload = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            incoming["name"],
            incoming["cas_number"],
            incoming["catalog_number"],
            incoming["specification"],
            incoming["manufacturer"],
            incoming["quantity"],
            incoming["quantity_unit"],
            incoming["status"],
            incoming["source"],
            incoming["raw_payload"],
            existing["id"],
        ),
    )
    row = connection.execute(
        "SELECT * FROM pending_orders WHERE id = ?",
        (existing["id"],),
    ).fetchone()
    if row is None:
        raise RuntimeError("Pending-order update did not return a row.")
    return row, False


def create_pending_order(
    data: Mapping[str, Any],
    db_path: str | Path | None = None,
    *,
    source: object = None,
) -> dict[str, Any]:
    """Create or safely update one locally staged pending order."""

    incoming = _normalize_order(data, source=source)
    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        with connection:
            row, created = _upsert_pending_order(connection, incoming)
    result = _row_to_dict(row)
    result["created"] = created
    return result


def import_pending_orders(
    orders: Sequence[Mapping[str, Any]],
    db_path: str | Path | None = None,
    *,
    source: object = None,
) -> list[dict[str, Any]]:
    """Atomically import a batch of externally supplied pending-order records."""

    if isinstance(orders, (str, bytes)) or not isinstance(orders, Sequence):
        raise PendingOrderValidationError("orders must be a sequence of mappings.")
    normalized_orders = [_normalize_order(order, source=source) for order in orders]
    references = [order["order_reference"] for order in normalized_orders]
    if len(set(references)) != len(references):
        raise PendingOrderValidationError(
            "An import batch may contain each order_reference only once."
        )

    resolved_db_path = init_db(db_path)
    results: list[dict[str, Any]] = []
    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        with connection:
            for incoming in normalized_orders:
                row, created = _upsert_pending_order(connection, incoming)
                result = _row_to_dict(row)
                result["created"] = created
                results.append(result)
    return results


def list_pending_orders(
    db_path: str | Path | None = None,
    *,
    status: str | None = "pending",
) -> list[dict[str, Any]]:
    """Return local order records in newest-first order, optionally by status."""

    if status is not None:
        normalized_status = _optional_text(status, "status")
        if normalized_status is None or normalized_status.casefold() not in PENDING_ORDER_STATUSES:
            allowed = ", ".join(sorted(PENDING_ORDER_STATUSES))
            raise PendingOrderValidationError(f"status must be one of: {allowed}.")
        normalized_status = normalized_status.casefold()
    else:
        normalized_status = None

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path)) as connection:
        connection.row_factory = sqlite3.Row
        if normalized_status is None:
            rows = connection.execute(
                "SELECT * FROM pending_orders ORDER BY created_at DESC, id DESC"
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM pending_orders
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalized_status,),
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _comparable(value: object) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).casefold()
    return normalized or None


def _normalize_receipt_for_match(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise PendingOrderValidationError("Receipt data must be a mapping.")
    name = _optional_text(_first_value(data, "name", "chemical_name"), "name")
    cas_number = _optional_cas(data.get("cas_number"))
    if name is None and cas_number is None:
        raise PendingOrderValidationError(
            "Receipt matching requires a chemical name or a valid CAS number."
        )
    return {
        "name": name,
        "cas_number": cas_number,
        "catalog_number": _optional_text(
            data.get("catalog_number"), "catalog_number"
        ),
        "specification": _optional_text(
            data.get("specification"), "specification"
        ),
        "manufacturer": _optional_text(data.get("manufacturer"), "manufacturer"),
        "quantity": _quantity(data.get("quantity")),
        "quantity_unit": _optional_text(
            _first_value(data, "quantity_unit", "unit"), "quantity_unit"
        )
        or "unit",
    }


def _quantity_score(receipt: Mapping[str, Any], order: Mapping[str, Any]) -> float:
    if _comparable(receipt["quantity_unit"]) != _comparable(order["quantity_unit"]):
        return 0.0
    expected = float(order["quantity"])
    observed = float(receipt["quantity"])
    if expected == observed:
        return 0.03
    if expected == 0:
        return 0.0
    relative_difference = abs(observed - expected) / abs(expected)
    if relative_difference <= 0.02:
        return 0.03
    if relative_difference <= 0.10:
        return 0.015
    return 0.0


def _score_order_match(
    receipt: Mapping[str, Any],
    order: Mapping[str, Any],
) -> tuple[float, list[str]] | None:
    # A conflicting validated CAS is a hard no-match.  The result should not
    # be rescued by a similar name or manufacturer.
    if (
        receipt["cas_number"] is not None
        and order["cas_number"] is not None
        and receipt["cas_number"] != order["cas_number"]
    ):
        return None

    score = 0.0
    details: list[str] = []
    if receipt["cas_number"] is not None and receipt["cas_number"] == order["cas_number"]:
        score += 0.65
        details.append("CAS exact")
    if (
        _comparable(receipt["catalog_number"])
        and _comparable(receipt["catalog_number"])
        == _comparable(order["catalog_number"])
    ):
        score += 0.15
        details.append("catalog exact")
    if (
        _comparable(receipt["manufacturer"])
        and _comparable(receipt["manufacturer"])
        == _comparable(order["manufacturer"])
    ):
        score += 0.10
        details.append("manufacturer exact")
    if (
        _comparable(receipt["specification"])
        and _comparable(receipt["specification"])
        == _comparable(order["specification"])
    ):
        score += 0.06
        details.append("specification exact")
    quantity_score = _quantity_score(receipt, order)
    if quantity_score:
        score += quantity_score
        details.append("quantity compatible")
    if _comparable(receipt["name"]) and _comparable(receipt["name"]) == _comparable(order["name"]):
        score += 0.01
        details.append("name exact")
    if not details:
        return None
    return min(round(score, 4), 1.0), details


def match_pending_orders(
    reagent_data: Mapping[str, Any],
    db_path: str | Path | None = None,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Rank active pending orders using only deterministic field comparisons."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise PendingOrderValidationError("limit must be a positive integer.")
    receipt = _normalize_receipt_for_match(reagent_data)
    orders = list_pending_orders(db_path, status="pending")
    candidates: list[dict[str, Any]] = []
    for order in orders:
        scored = _score_order_match(receipt, order)
        if scored is None:
            continue
        score, details = scored
        candidates.append(
            {
                "id": order["id"],
                "order_reference": order["order_reference"],
                "order_id": order["order_reference"],
                "chemical_name": order["name"],
                "name": order["name"],
                "cas_number": order["cas_number"],
                "catalog_number": order["catalog_number"],
                "specification": order["specification"],
                "manufacturer": order["manufacturer"],
                "quantity": order["quantity"],
                "quantity_unit": order["quantity_unit"],
                "score": score,
                "score_percent": f"{score:.0%}",
                "explanation": "; ".join(details) + ".",
            }
        )
    candidates.sort(key=lambda item: (-float(item["score"]), str(item["order_reference"])))
    return candidates[:limit]


def select_unique_order_match(
    candidates: Sequence[Mapping[str, Any]],
    *,
    min_score: float = 0.85,
    ambiguity_margin: float = 0.10,
) -> dict[str, Any] | None:
    """Return one high-confidence candidate only when it is clearly separated."""

    if not 0 <= min_score <= 1:
        raise PendingOrderValidationError("min_score must be a number from 0 to 1.")
    if ambiguity_margin < 0:
        raise PendingOrderValidationError("ambiguity_margin must be non-negative.")
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        try:
            score = float(item["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PendingOrderValidationError(
                "Each candidate requires a numeric score."
            ) from exc
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise PendingOrderValidationError(
                "Each candidate score must be a finite number from 0 to 1."
            )
        item["score"] = score
        ranked.append(item)
    ranked.sort(
        key=lambda item: (-float(item["score"]), str(item.get("order_reference", "")))
    )
    if not ranked:
        return None
    leading_score = float(ranked[0]["score"])
    if not math.isfinite(leading_score) or leading_score < min_score:
        return None
    if len(ranked) > 1:
        next_score = float(ranked[1]["score"])
        if leading_score - next_score < ambiguity_margin:
            return None
    return ranked[0]


def mark_order_received(
    order_reference: object,
    reagent_id: object,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Link a human-confirmed reagent to exactly one pending order."""

    normalized_reference = _required_text(order_reference, "order_reference")
    if isinstance(reagent_id, bool):
        raise PendingOrderValidationError("reagent_id must be a positive integer.")
    try:
        normalized_reagent_id = int(reagent_id)
    except (TypeError, ValueError) as exc:
        raise PendingOrderValidationError(
            "reagent_id must be a positive integer."
        ) from exc
    if normalized_reagent_id < 1 or normalized_reagent_id != reagent_id:
        raise PendingOrderValidationError("reagent_id must be a positive integer.")

    resolved_db_path = init_db(db_path)
    with closing(sqlite3.connect(resolved_db_path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        with connection:
            order = connection.execute(
                "SELECT * FROM pending_orders WHERE order_reference = ?",
                (normalized_reference,),
            ).fetchone()
            if order is None:
                raise PendingOrderValidationError(
                    f"Pending order {normalized_reference!r} was not found."
                )
            reagent = connection.execute(
                "SELECT id FROM reagents WHERE id = ?",
                (normalized_reagent_id,),
            ).fetchone()
            if reagent is None:
                raise PendingOrderValidationError(
                    f"Reagent ID {normalized_reagent_id} was not found."
                )
            if order["status"] == "received":
                if order["received_reagent_id"] == normalized_reagent_id:
                    return _row_to_dict(order)
                raise PendingOrderConflictError(
                    "This order is already linked to a different received reagent."
                )
            if order["status"] == "cancelled":
                raise PendingOrderConflictError(
                    "A cancelled order cannot be marked received without manual reconciliation."
                )
            connection.execute(
                """
                UPDATE pending_orders
                SET
                    status = 'received',
                    received_reagent_id = ?,
                    received_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (normalized_reagent_id, order["id"]),
            )
            updated = connection.execute(
                "SELECT * FROM pending_orders WHERE id = ?",
                (order["id"],),
            ).fetchone()
    if updated is None:
        raise RuntimeError("Pending-order receipt update did not return a row.")
    return _row_to_dict(updated)
