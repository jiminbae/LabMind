"""End-to-end LabMind label analysis pipeline."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from .date_utils import normalize_expiry_date
from .expiry_service import check_expiry, resolve_effective_expiry
from .inventory_service import DEFAULT_INVENTORY_PATH, InventoryRepository
from .product_service import DEFAULT_PRODUCTS_PATH, ProductRepository
from .provider_config import DEFAULT_ENV_PATH
from .recommendation_service import (
    DEFAULT_ALTERNATIVES_PATH,
    AlternativeRepository,
)
from .schemas import AnalysisResult, OCRResult, ResultStatus
from .vision_gateway import extract_label_with_provider


def _failed_analysis(ocr: OCRResult, message: str) -> AnalysisResult:
    return AnalysisResult(
        status=ResultStatus.FAILED,
        ocr=ocr,
        error_message=message,
    )


def _needs_alternatives(inventory_found: bool, quantity: int | None, should_alert: bool) -> bool:
    return not inventory_found or quantity == 0 or should_alert


def analyze_label(
    image_path: str | Path,
    *,
    mode: str | None = None,
    provider: str | None = None,
    warning_days: int = 30,
    today: date | datetime | None = None,
    client: Any | None = None,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
    inventory_path: str | Path = DEFAULT_INVENTORY_PATH,
    products_path: str | Path = DEFAULT_PRODUCTS_PATH,
    alternatives_path: str | Path = DEFAULT_ALTERNATIVES_PATH,
    ocr_result: OCRResult | None = None,
) -> AnalysisResult:
    """Run OCR, inventory, expiry, product, and recommendation analysis.

    ``ocr_result`` is an optional test/integration hook. Production callers
    should omit it and provide an image path.
    """

    ocr = ocr_result or extract_label_with_provider(
        image_path,
        mode=mode,
        provider=provider,
        client=client,
        environ=environ,
        env_path=env_path,
    )

    if ocr.status is ResultStatus.FAILED:
        return _failed_analysis(
            ocr,
            ocr.error_message or "Label recognition failed.",
        )

    if not ocr.catalog_number:
        return _failed_analysis(ocr, "Catalog number could not be recognized.")

    try:
        inventory_repository = InventoryRepository(inventory_path)
        product_repository = ProductRepository(products_path)

        inventory = inventory_repository.find_by_catalog_number(ocr.catalog_number)
        product = product_repository.find_by_catalog_number(ocr.catalog_number)

        image_expiry = normalize_expiry_date(ocr.expiry_date)
        inventory_expiry = inventory.expiry_date if inventory.found else None
        effective_expiry, expiry_mismatch = resolve_effective_expiry(
            image_expiry,
            inventory_expiry,
        )
        expiry_warning = check_expiry(
            effective_expiry,
            warning_days=warning_days,
            today=today,
        )

        alternatives = []
        if _needs_alternatives(
            inventory_found=inventory.found,
            quantity=inventory.quantity,
            should_alert=expiry_warning.should_alert,
        ):
            alternative_repository = AlternativeRepository(
                alternatives_path=alternatives_path,
                products_path=products_path,
            )
            alternatives = alternative_repository.find_by_catalog_number(
                ocr.catalog_number
            )

        return AnalysisResult(
            status=ResultStatus.SUCCESS,
            ocr=ocr,
            inventory=inventory,
            expiry_warning=expiry_warning,
            alternatives=alternatives,
            product=product,
            expiry_mismatch=expiry_mismatch,
            image_expiry=image_expiry,
            inventory_expiry=inventory_expiry,
        )
    except Exception as error:
        return _failed_analysis(
            ocr,
            f"Backend analysis failed ({type(error).__name__}).",
        )
