"""CSV-backed supplier product catalog service."""

from __future__ import annotations

import csv
from pathlib import Path

from .inventory_service import normalize_catalog_number
from .schemas import ProductInfo


DEFAULT_PRODUCTS_PATH = Path(__file__).resolve().parents[1] / "products.csv"
REQUIRED_FIELDS = {
    "brand",
    "catalog_number",
    "volume_ml",
    "diameter_mm",
    "height_mm",
    "pack_size",
    "price_usd",
    "unit_price_usd",
    "url",
}


def _optional_float(value: str | None, field_name: str, row_number: int) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(
            f"Invalid {field_name} on products row {row_number}"
        ) from error
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative on products row {row_number}")
    return number


def _optional_int(value: str | None, field_name: str, row_number: int) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(
            f"Invalid {field_name} on products row {row_number}"
        ) from error
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative on products row {row_number}")
    return number


class ProductRepository:
    """Load the supplier catalog once and provide product lookups."""

    def __init__(self, products_path: str | Path = DEFAULT_PRODUCTS_PATH) -> None:
        self.products_path = Path(products_path)
        self._products = self._load_products()

    def _load_products(self) -> dict[str, ProductInfo]:
        if not self.products_path.is_file():
            raise FileNotFoundError(f"Products file not found: {self.products_path}")

        products: dict[str, ProductInfo] = {}
        with self.products_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual_fields = set(reader.fieldnames or [])
            missing_fields = REQUIRED_FIELDS - actual_fields
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"Products CSV is missing required fields: {missing}")

            for row_number, row in enumerate(reader, start=2):
                catalog_number = normalize_catalog_number(row["catalog_number"])
                if not catalog_number:
                    raise ValueError(f"Missing catalog_number on products row {row_number}")
                if catalog_number in products:
                    raise ValueError(
                        f"Duplicate catalog_number in products: {catalog_number}"
                    )

                products[catalog_number] = ProductInfo(
                    found=True,
                    catalog_number=catalog_number,
                    brand=row["brand"].strip() or None,
                    volume_ml=_optional_float(row["volume_ml"], "volume_ml", row_number),
                    diameter_mm=_optional_float(
                        row["diameter_mm"], "diameter_mm", row_number
                    ),
                    height_mm=_optional_float(row["height_mm"], "height_mm", row_number),
                    pack_size=_optional_int(row["pack_size"], "pack_size", row_number),
                    price_usd=_optional_float(row["price_usd"], "price_usd", row_number),
                    unit_price_usd=_optional_float(
                        row["unit_price_usd"], "unit_price_usd", row_number
                    ),
                    url=row["url"].strip() or None,
                )

        return products

    def find_by_catalog_number(self, catalog_number: str | None) -> ProductInfo:
        normalized = normalize_catalog_number(catalog_number)
        product = self._products.get(normalized)
        if product is not None:
            return product
        return ProductInfo(found=False, catalog_number=normalized)


def enrich_product_information(
    catalog_number: str | None,
    products_path: str | Path = DEFAULT_PRODUCTS_PATH,
) -> ProductInfo:
    """Convenience wrapper for a single supplier product lookup."""

    return ProductRepository(products_path).find_by_catalog_number(catalog_number)
