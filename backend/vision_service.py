"""Safe, opt-in Gemini extraction for five reagent-label fields.

No sample values are returned on failure.  The caller receives a structured
manual-entry state instead, so a missing key or provider outage can never turn
into a plausible-looking reagent record.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .cas_validator import validate_cas_details
from .provider_config import DEFAULT_ENV_PATH, resolve_gemini_config
from .provider_errors import provider_failure_message


SUPPORTED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
FIELD_LABELS = {
    "chemical_name": "chemical name",
    "cas_number": "CAS number",
    "specification": "specification",
    "batch_number": "batch or lot number",
    "manufacturer": "manufacturer",
}

LABEL_PROMPT = """You extract only visible printed information from a laboratory
reagent label. Return JSON for exactly these fields:

- chemical_name: the visible chemical or product name exactly as printed,
  including salt, hydrate, and stereochemical notation, or null when absent.
- cas_number: the CAS Registry Number, including hyphens, or null when absent.
- specification: a visible grade, assay, concentration, or specification, or null.
- batch_number: a visible lot or batch number, or null.
- manufacturer: the visible manufacturer or brand, or null.
- confidence: a number from 0 to 1 that reflects the overall clarity of the
  returned fields.

Do not infer chemistry, hazards, storage, a catalog number, quantity, volume,
or an expiry date. Never derive or normalize a missing name from the CAS number,
manufacturer, or another field. Do not guess. Preserve printed text where
possible. A local CAS checksum check will validate the result after extraction.
"""


class LabelExtraction(BaseModel):
    """Gemini structured-output schema for the current intake UI."""

    chemical_name: str | None = Field(
        description="Chemical or product name visibly printed on the label, unchanged."
    )
    cas_number: str | None = Field(
        description="CAS Registry Number visibly printed on the label, including hyphens."
    )
    specification: str | None = Field(
        description="Visible grade, assay, concentration, or specification."
    )
    batch_number: str | None = Field(
        description="Visible lot or batch identifier."
    )
    manufacturer: str | None = Field(
        description="Manufacturer or brand visibly printed on the label."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence based only on the clarity of visible fields.",
    )


@dataclass(frozen=True, slots=True)
class LabelExtractionResult:
    """UI-safe outcome that never includes a secret or raw provider response."""

    status: str
    fields: dict[str, Any]
    message: str
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blank_fields() -> dict[str, Any]:
    return {**{field: "" for field in FIELD_LABELS}, "confidence": 0}


def _manual_result(
    message: str,
    *,
    provider: str | None = None,
) -> LabelExtractionResult:
    return LabelExtractionResult(
        status="manual",
        fields=_blank_fields(),
        message=message,
        provider=provider,
    )


def _failed_result(
    message: str,
    *,
    provider: str | None = None,
) -> LabelExtractionResult:
    return LabelExtractionResult(
        status="failed",
        fields=_blank_fields(),
        message=message,
        provider=provider,
    )


def _validate_upload(image_bytes: bytes, filename: str) -> tuple[str, str]:
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("The label image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("The label image exceeds the 10 MB safety limit.")
    suffix = filename.lower().rpartition(".")[2]
    extension = f".{suffix}" if suffix else ""
    if extension not in SUPPORTED_SUFFIXES:
        formats = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"Unsupported image format. Use one of: {formats}.")
    signatures_match = {
        ".png": image_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": image_bytes.startswith(b"\xff\xd8\xff"),
        ".jpeg": image_bytes.startswith(b"\xff\xd8\xff"),
        ".webp": (
            len(image_bytes) >= 12
            and image_bytes.startswith(b"RIFF")
            and image_bytes[8:12] == b"WEBP"
        ),
    }
    if not signatures_match[extension]:
        raise ValueError("The file contents do not match the selected image format.")
    mime_type = MIME_TYPES[extension]
    return extension, mime_type


def _create_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "The google-genai package is not installed. Install requirements.txt."
        ) from error
    return genai.Client(api_key=api_key)


def _response_to_model(response: Any) -> LabelExtraction:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, LabelExtraction):
        return parsed
    if isinstance(parsed, dict):
        return LabelExtraction.model_validate(parsed)

    text = getattr(response, "text", None)
    if not text:
        raise ValueError("The vision provider returned no structured result.")
    return LabelExtraction.model_validate(json.loads(text))


def _clean_text(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _to_result(extraction: LabelExtraction) -> LabelExtractionResult:
    cas_number = _clean_text(extraction.cas_number)
    cas_check = validate_cas_details(cas_number)
    fields: dict[str, Any] = {
        "chemical_name": _clean_text(extraction.chemical_name) or "",
        "cas_number": "",
        "specification": _clean_text(extraction.specification) or "",
        "batch_number": _clean_text(extraction.batch_number) or "",
        "manufacturer": _clean_text(extraction.manufacturer) or "",
        "confidence": round(float(extraction.confidence) * 100),
    }

    if cas_number and cas_check.is_valid and cas_check.normalized_cas:
        fields["cas_number"] = cas_check.normalized_cas
    elif cas_number:
        fields["cas_number"] = ""
        return LabelExtractionResult(
            status="partial",
            fields=fields,
            message=(
                "The provider read a CAS-like value, but its check digit failed. "
                "Enter or recapture the CAS number manually."
            ),
            provider="gemini",
        )
    else:
        fields["cas_number"] = ""

    recognized = any(fields[field] for field in FIELD_LABELS)
    if not recognized:
        return _manual_result(
            "No supported label fields were visible. Enter the details manually.",
            provider="gemini",
        )

    missing = [label for field, label in FIELD_LABELS.items() if not fields[field]]
    if missing:
        return LabelExtractionResult(
            status="partial",
            fields=fields,
            message=(
                "Some label fields were extracted. Review them; the image did not "
                f"provide {', '.join(missing)}."
            ),
            provider="gemini",
        )
    return LabelExtractionResult(
        status="success",
        fields=fields,
        message="Label fields are ready for review. Verify every value before continuing.",
        provider="gemini",
    )


def extract_label_fields(
    image_bytes: bytes,
    filename: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_path=DEFAULT_ENV_PATH,
    client: Any | None = None,
) -> LabelExtractionResult:
    """Extract the five allowed fields, or return a safe manual-entry outcome.

    ``client`` is injectable for deterministic tests.  The public API catches
    expected provider errors so the Streamlit app can continue in manual mode.
    """

    try:
        _, mime_type = _validate_upload(image_bytes, filename)
    except ValueError as error:
        return _failed_result(str(error))

    try:
        config = resolve_gemini_config(environ=environ, env_path=env_path)
    except ValueError as error:
        return _failed_result(str(error))

    if config.mode == "manual":
        return _manual_result(
            "Vision extraction is not configured. Enter the label fields manually."
        )
    if not config.api_key:
        return _manual_result(
            "Vision extraction is enabled, but GEMINI_API_KEY is not configured. "
            "Enter the label fields manually."
        )

    try:
        active_client = client or _create_client(config.api_key)
        try:
            from google.genai import types
        except ImportError:
            if client is None:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "The google-genai package is not installed. Install requirements.txt."
                )
            # Dependency-free fake clients can exercise parsing and error
            # handling in tests without a network SDK installed.
            response = active_client.models.generate_content(
                model=config.model,
                contents=[image_bytes, LABEL_PROMPT],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": LabelExtraction,
                },
            )
        else:
            response = active_client.models.generate_content(
                model=config.model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    LABEL_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LabelExtraction,
                ),
            )
        return _to_result(_response_to_model(response))
    except Exception as error:  # The UI must not leak raw provider failures.
        return _failed_result(
            provider_failure_message(
                error,
                operation="Vision extraction",
                fallback="Enter the label fields manually and retry later.",
            ),
            provider="gemini",
        )
