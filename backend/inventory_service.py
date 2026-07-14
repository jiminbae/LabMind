"""CSV-backed inventory lookup service."""

from __future__ import annotations

import csv
from pathlib import Path

from .date_utils import normalize_expiry_date
from .schemas import InventoryItem


DEFAULT_INVENTORY_PATH = Path(__file__).resolve().parents[1] / "inventory.csv"
REQUIRED_FIELDS = {
    "catalog_number",
    "brand",
    "expiry_date",
    "quantity",
    "location",
}


def normalize_catalog_number(catalog_number: str | None) -> str:
    """Normalize a catalog number for display and case-insensitive lookup."""

    return "" if catalog_number is None else str(catalog_number).strip().upper()


class InventoryRepository:
    """Load inventory once and provide catalog-number lookups."""

    def __init__(self, inventory_path: str | Path = DEFAULT_INVENTORY_PATH) -> None:
        self.inventory_path = Path(inventory_path)
        self._items = self._load_items()

    def _load_items(self) -> dict[str, InventoryItem]:
        if not self.inventory_path.is_file():
            raise FileNotFoundError(f"Inventory file not found: {self.inventory_path}")

        items: dict[str, InventoryItem] = {}
        with self.inventory_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual_fields = set(reader.fieldnames or [])
            missing_fields = REQUIRED_FIELDS - actual_fields
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"Inventory CSV is missing required fields: {missing}")

            for row_number, row in enumerate(reader, start=2):
                catalog_number = normalize_catalog_number(row["catalog_number"])
                if not catalog_number:
                    raise ValueError(f"Missing catalog_number on inventory row {row_number}")

                try:
                    quantity = int(row["quantity"])
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid quantity on inventory row {row_number}"
                    ) from error

                expiry_date = normalize_expiry_date(row["expiry_date"])
                if row["expiry_date"].strip() and expiry_date is None:
                    raise ValueError(
                        f"Invalid expiry_date on inventory row {row_number}"
                    )

                if catalog_number in items:
                    raise ValueError(
                        f"Duplicate catalog_number in inventory: {catalog_number}"
                    )

                items[catalog_number] = InventoryItem(
                    found=True,
                    catalog_number=catalog_number,
                    brand=row["brand"].strip() or None,
                    expiry_date=expiry_date,
                    quantity=quantity,
                    location=row["location"].strip() or None,
                )

        return items

    def find_by_catalog_number(self, catalog_number: str | None) -> InventoryItem:
        normalized = normalize_catalog_number(catalog_number)
        item = self._items.get(normalized)
        if item is not None:
            return item
        return InventoryItem(found=False, catalog_number=normalized)


def find_inventory_item(
    catalog_number: str | None,
    inventory_path: str | Path = DEFAULT_INVENTORY_PATH,
) -> InventoryItem:
    """Convenience wrapper for a single inventory lookup."""

    return InventoryRepository(inventory_path).find_by_catalog_number(catalog_number)
