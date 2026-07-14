"""Rule-based alternative-product recommendation service."""

from __future__ import annotations

import csv
from pathlib import Path

from .inventory_service import normalize_catalog_number
from .product_service import DEFAULT_PRODUCTS_PATH, ProductRepository
from .schemas import AlternativeRecommendation


DEFAULT_ALTERNATIVES_PATH = Path(__file__).resolve().parents[1] / "alternatives.csv"
REQUIRED_FIELDS = {
    "original_catalog",
    "alternative_catalog",
    "compatibility_note",
}


class AlternativeRepository:
    """Load reviewed catalog mappings and enrich them with supplier data."""

    def __init__(
        self,
        alternatives_path: str | Path = DEFAULT_ALTERNATIVES_PATH,
        products_path: str | Path = DEFAULT_PRODUCTS_PATH,
    ) -> None:
        self.alternatives_path = Path(alternatives_path)
        self.product_repository = ProductRepository(products_path)
        self._alternatives = self._load_alternatives()

    def _load_alternatives(self) -> dict[str, list[AlternativeRecommendation]]:
        if not self.alternatives_path.is_file():
            raise FileNotFoundError(
                f"Alternatives file not found: {self.alternatives_path}"
            )

        alternatives: dict[str, list[AlternativeRecommendation]] = {}
        seen_pairs: set[tuple[str, str]] = set()

        with self.alternatives_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            actual_fields = set(reader.fieldnames or [])
            missing_fields = REQUIRED_FIELDS - actual_fields
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"Alternatives CSV is missing required fields: {missing}")

            for row_number, row in enumerate(reader, start=2):
                original = normalize_catalog_number(row["original_catalog"])
                alternative = normalize_catalog_number(row["alternative_catalog"])
                note = row["compatibility_note"].strip()

                if not original or not alternative:
                    raise ValueError(
                        f"Missing catalog number on alternatives row {row_number}"
                    )
                if original == alternative:
                    raise ValueError(
                        f"A product cannot recommend itself on alternatives row {row_number}"
                    )
                if not note:
                    raise ValueError(
                        f"Missing compatibility_note on alternatives row {row_number}"
                    )

                pair = (original, alternative)
                if pair in seen_pairs:
                    raise ValueError(
                        f"Duplicate alternative mapping: {original} -> {alternative}"
                    )
                seen_pairs.add(pair)

                product = self.product_repository.find_by_catalog_number(alternative)
                if not product.found:
                    raise ValueError(
                        f"Alternative product is missing from products.csv: {alternative}"
                    )

                alternatives.setdefault(original, []).append(
                    AlternativeRecommendation(
                        catalog_number=alternative,
                        compatibility_note=note,
                        product=product,
                    )
                )

        return alternatives

    def find_by_catalog_number(
        self, catalog_number: str | None
    ) -> list[AlternativeRecommendation]:
        normalized = normalize_catalog_number(catalog_number)
        return list(self._alternatives.get(normalized, []))


def find_alternatives(
    catalog_number: str | None,
    alternatives_path: str | Path = DEFAULT_ALTERNATIVES_PATH,
    products_path: str | Path = DEFAULT_PRODUCTS_PATH,
) -> list[AlternativeRecommendation]:
    """Return reviewed and product-enriched alternatives for one item."""

    return AlternativeRepository(
        alternatives_path=alternatives_path,
        products_path=products_path,
    ).find_by_catalog_number(catalog_number)
