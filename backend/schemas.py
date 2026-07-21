"""Shared data structures for the LabMind backend.

Every service returns one of these dataclasses.  The UI should consume the
result of ``to_dict()`` instead of depending on service implementation details.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ResultStatus(str, Enum):
    """Overall success state for OCR and pipeline operations."""

    SUCCESS = "success"
    FAILED = "failed"


class ExpiryState(str, Enum):
    """Normalized state of an item's effective expiry date."""

    UNKNOWN = "unknown"
    VALID = "valid"
    WARNING = "warning"
    EXPIRED = "expired"


class SerializableSchema:
    """Mixin that converts nested schema objects into JSON-ready dictionaries."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OCRResult(SerializableSchema):
    """Structured information extracted from one label image."""

    catalog_number: str | None = None
    lot_number: str | None = None
    expiry_date: str | None = None
    brand: str | None = None
    product_name: str | None = None
    confidence: float = 0.0
    status: ResultStatus = ResultStatus.SUCCESS
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.status is ResultStatus.FAILED and not self.error_message:
            raise ValueError("failed OCR results must include error_message")


@dataclass(slots=True)
class InventoryItem(SerializableSchema):
    """Inventory lookup result for a catalog number."""

    found: bool
    catalog_number: str
    brand: str | None = None
    expiry_date: str | None = None
    quantity: int | None = None
    location: str | None = None

    def __post_init__(self) -> None:
        if self.quantity is not None and self.quantity < 0:
            raise ValueError("quantity cannot be negative")


@dataclass(slots=True)
class ExpiryWarning(SerializableSchema):
    """Result of comparing an effective expiry date with a warning window."""

    state: ExpiryState
    effective_expiry_date: str | None = None
    days_remaining: int | None = None
    warning_days: int = 30
    should_alert: bool = False

    def __post_init__(self) -> None:
        if self.warning_days < 0:
            raise ValueError("warning_days cannot be negative")


@dataclass(slots=True)
class ProductInfo(SerializableSchema):
    """Supplier catalog information used to enrich results and purchase orders."""

    found: bool
    catalog_number: str
    brand: str | None = None
    volume_ml: float | None = None
    diameter_mm: float | None = None
    height_mm: float | None = None
    pack_size: int | None = None
    price_usd: float | None = None
    unit_price_usd: float | None = None
    url: str | None = None


@dataclass(slots=True)
class AlternativeRecommendation(SerializableSchema):
    """One compatible alternative product."""

    catalog_number: str
    compatibility_note: str
    product: ProductInfo | None = None


@dataclass(slots=True)
class AnalysisResult(SerializableSchema):
    """Stable response returned by the future ``analyze_label`` pipeline."""

    status: ResultStatus
    ocr: OCRResult
    inventory: InventoryItem | None = None
    expiry_warning: ExpiryWarning | None = None
    alternatives: list[AlternativeRecommendation] = field(default_factory=list)
    product: ProductInfo | None = None
    expiry_mismatch: bool = False
    image_expiry: str | None = None
    inventory_expiry: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status is ResultStatus.FAILED and not self.error_message:
            self.error_message = self.ocr.error_message or "Analysis failed."
