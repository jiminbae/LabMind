"""Optional Gemini translation from natural language to safe inventory filters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

from .classification_service import CHEMICAL_LABEL_OPTIONS
from .provider_config import DEFAULT_ENV_PATH, resolve_gemini_config
from .provider_errors import provider_failure_message


MAX_QUESTION_LENGTH = 600
MAX_FILTER_LABELS = 6

QUERY_PROMPT = """Translate one laboratory inventory question into a constrained
inventory-filter object. Return JSON only with these fields:

- chemical_name: a name or abbreviation explicitly requested, otherwise null.
- cas_number: a CAS number explicitly requested, otherwise null.
- manufacturer: a manufacturer explicitly requested, otherwise null.
- storage_location: a storage location explicitly requested, otherwise null.
- show_all: true only when the user explicitly asks to see the entire inventory;
  otherwise false.
- status: exactly one of any, available, out_of_stock, expired, expiring_soon.
- expiry_within_days: a non-negative day window, otherwise null.
- minimum_quantity and maximum_quantity: integer container-count bounds.
- minimum_volume_ml and maximum_volume_ml: per-container volume bounds in mL.
- chemical_labels: zero or more values only from the supplied allowlist.

Do not answer whether anything is in stock. Do not create SQL, SMARTS, code, or
chemical structures. Do not invent a filter that the question did not request.
Use status=any unless the question explicitly asks about availability, expiry,
or out-of-stock records.

Allowed chemical labels: {chemical_labels}
"""


class InventoryFilterTranslation(BaseModel):
    chemical_name: str | None = None
    cas_number: str | None = None
    manufacturer: str | None = None
    storage_location: str | None = None
    show_all: bool = False
    status: Literal[
        "any",
        "available",
        "out_of_stock",
        "expired",
        "expiring_soon",
    ] = "any"
    expiry_within_days: int | None = Field(default=None, ge=0, le=3650)
    minimum_quantity: int | None = Field(default=None, ge=0)
    maximum_quantity: int | None = Field(default=None, ge=0)
    minimum_volume_ml: float | None = Field(default=None, ge=0)
    maximum_volume_ml: float | None = Field(default=None, ge=0)
    chemical_labels: list[str] = Field(default_factory=list, max_length=MAX_FILTER_LABELS)


@dataclass(frozen=True, slots=True)
class QueryTranslationResult:
    status: str
    translation: dict[str, Any] | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _create_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as error:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "The google-genai package is not installed. Install requirements.txt."
        ) from error
    return genai.Client(api_key=api_key)


def _response_to_model(response: Any) -> InventoryFilterTranslation:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, InventoryFilterTranslation):
        return parsed
    if isinstance(parsed, dict):
        return InventoryFilterTranslation.model_validate(parsed)
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("The query provider returned no structured result.")
    return InventoryFilterTranslation.model_validate(json.loads(text))


def _optional_text(value: str | None) -> str | None:
    normalized = value.strip() if isinstance(value, str) else ""
    return normalized or None


def _safe_labels(values: list[str]) -> list[str]:
    canonical = {label.casefold(): label for label in CHEMICAL_LABEL_OPTIONS}
    accepted: list[str] = []
    for value in values:
        normalized = value.strip().casefold() if isinstance(value, str) else ""
        label = canonical.get(normalized)
        if label and label not in accepted:
            accepted.append(label)
    return accepted[:MAX_FILTER_LABELS]


def translate_inventory_question(
    question: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_path=DEFAULT_ENV_PATH,
    client: Any | None = None,
) -> QueryTranslationResult:
    """Return model-generated filter values, never an inventory answer."""

    normalized_question = question.strip()
    if not normalized_question:
        return QueryTranslationResult("failed", None, "Enter an inventory question.")
    if len(normalized_question) > MAX_QUESTION_LENGTH:
        return QueryTranslationResult(
            "failed",
            None,
            f"Keep inventory questions under {MAX_QUESTION_LENGTH} characters.",
        )

    try:
        config = resolve_gemini_config(environ=environ, env_path=env_path)
    except ValueError as error:
        return QueryTranslationResult("failed", None, str(error))
    if config.mode != "live" or not config.api_key:
        return QueryTranslationResult(
            "manual",
            None,
            "AI inventory filtering is not configured for this question.",
        )

    prompt = (
        QUERY_PROMPT.format(
            chemical_labels=", ".join(sorted(CHEMICAL_LABEL_OPTIONS)),
        )
        + f"\nQuestion: {normalized_question}"
    )
    try:
        active_client = client or _create_client(config.api_key)
        try:
            from google.genai import types
        except ImportError:
            if client is None:
                raise RuntimeError(
                    "The google-genai package is not installed. Install requirements.txt."
                )
            response = active_client.models.generate_content(
                model=config.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": InventoryFilterTranslation,
                },
            )
        else:
            response = active_client.models.generate_content(
                model=config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InventoryFilterTranslation,
                ),
            )
        parsed = _response_to_model(response)
    except Exception as error:  # Do not surface raw provider internals or crash search.
        return QueryTranslationResult(
            "failed",
            None,
            provider_failure_message(
                error,
                operation="Inventory question translation",
                fallback="Try a chemical name, CAS number, or a simpler filter.",
            ),
        )

    translation = {
        "chemical_name": _optional_text(parsed.chemical_name),
        "cas_number": _optional_text(parsed.cas_number),
        "manufacturer": _optional_text(parsed.manufacturer),
        "storage_location": _optional_text(parsed.storage_location),
        "show_all": parsed.show_all,
        "status": parsed.status,
        "expiry_within_days": parsed.expiry_within_days,
        "minimum_quantity": parsed.minimum_quantity,
        "maximum_quantity": parsed.maximum_quantity,
        "minimum_volume_ml": parsed.minimum_volume_ml,
        "maximum_volume_ml": parsed.maximum_volume_ml,
        "chemical_labels": _safe_labels(parsed.chemical_labels),
    }
    has_filter = translation["show_all"] or any(
        value not in (None, "", [], "any", False)
        for key, value in translation.items()
        if key != "show_all"
    )
    if not has_filter:
        return QueryTranslationResult(
            "manual",
            None,
            "I could not identify an inventory filter. Include a chemical name, "
            "CAS number, manufacturer, quantity, expiry, location, or chemical label.",
        )
    return QueryTranslationResult(
        "success",
        translation,
        "The question was translated into inventory filters for local verification.",
    )
