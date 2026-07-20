"""OpenAI vision service for extracting reagent-label fields.

The service defaults to ``mock`` mode so local development and UI work do not
make billable API requests accidentally. Set ``LABMIND_VISION_MODE=live`` to
use the OpenAI Responses API.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .date_utils import normalize_expiry_date
from .schemas import OCRResult, ResultStatus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"
DEFAULT_MODEL = "gpt-4o"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


SYSTEM_PROMPT = """You extract structured information from laboratory reagent labels.

Background:
LabMind uses the result to query inventory and generate expiry warnings. Read
only information visibly supported by the photographed label. Never guess a
catalog number, lot number, date, brand, or product name.

Task:
Extract catalog_number, lot_number, expiry_date, brand, product_name, and a
confidence score from 0 to 1. Use null for fields that are not visible. Preserve
the label's date text; application code will normalize it.

Examples:
1. Label text "Sigma-Aldrich / Cat. No. HS4323K / Lot 24A01 / EXP 09/26"
   means catalog_number=HS4323K, lot_number=24A01,
   expiry_date=EXP 09/26, brand=Sigma-Aldrich.
2. If a label shows a brand and lot number but no catalog number, return
   catalog_number=null rather than inventing one.
"""


USER_PROMPT = (
    "Extract the reagent-label fields from this image. Focus on printed label "
    "text and return only the requested structured result."
)


class LabelExtraction(BaseModel):
    """Schema sent to the OpenAI Structured Outputs parser."""

    catalog_number: str | None
    lot_number: str | None
    expiry_date: str | None
    brand: str | None
    product_name: str | None
    confidence: float = Field(ge=0.0, le=1.0)


def _failed(message: str) -> OCRResult:
    return OCRResult(
        status=ResultStatus.FAILED,
        confidence=0.0,
        error_message=message,
    )


def _load_local_api_key(env_path: Path = DEFAULT_ENV_PATH) -> None:
    """Load OPENAI_API_KEY from a local env file without logging its value."""

    if os.environ.get("OPENAI_API_KEY") or not env_path.is_file():
        return

    with env_path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != "OPENAI_API_KEY":
                continue
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ["OPENAI_API_KEY"] = value
            return


def _validate_image_path(image_path: str | Path) -> Path:
    path = Path(image_path)
    if not path.is_file():
        raise ValueError("Image file does not exist.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported image format. Use one of: {supported}.")
    if path.stat().st_size == 0:
        raise ValueError("Image file is empty.")
    return path


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _create_openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError(
            "The openai package is not installed. Install requirements.txt."
        ) from error
    return OpenAI(api_key=api_key)


def _mock_result() -> OCRResult:
    return OCRResult(
        catalog_number="HS4323K",
        lot_number="DEMO-LOT-001",
        expiry_date="2026-07-25",
        brand="Sigma-Aldrich",
        product_name="1.5 mL microcentrifuge tube",
        confidence=0.99,
        status=ResultStatus.SUCCESS,
    )


def _parse_live_response(parsed: LabelExtraction | None) -> OCRResult:
    if parsed is None:
        return _failed("Vision API returned no structured result.")

    catalog_number = (
        parsed.catalog_number.strip().upper() if parsed.catalog_number else None
    )
    lot_number = parsed.lot_number.strip() if parsed.lot_number else None
    expiry_date = normalize_expiry_date(parsed.expiry_date)
    brand = parsed.brand.strip() if parsed.brand else None
    product_name = parsed.product_name.strip() if parsed.product_name else None
    confidence = float(parsed.confidence)

    if not catalog_number:
        return OCRResult(
            catalog_number=None,
            lot_number=lot_number,
            expiry_date=expiry_date,
            brand=brand,
            product_name=product_name,
            confidence=confidence,
            status=ResultStatus.FAILED,
            error_message="Catalog number could not be recognized.",
        )

    return OCRResult(
        catalog_number=catalog_number,
        lot_number=lot_number,
        expiry_date=expiry_date,
        brand=brand,
        product_name=product_name,
        confidence=confidence,
        status=ResultStatus.SUCCESS,
    )


def extract_label_info(
    image_path: str | Path,
    *,
    mode: str | None = None,
    model: str | None = None,
    client: Any | None = None,
) -> OCRResult:
    """Extract label fields in ``mock`` or ``live`` mode.

    A client may be injected for tests. All expected failures are returned as a
    valid ``OCRResult`` so the Streamlit UI does not crash.
    """

    try:
        path = _validate_image_path(image_path)
    except (OSError, ValueError) as error:
        return _failed(str(error))

    selected_mode = (mode or os.getenv("LABMIND_VISION_MODE", "mock")).lower()
    if selected_mode == "mock":
        return _mock_result()
    if selected_mode != "live":
        return _failed("LABMIND_VISION_MODE must be 'mock' or 'live'.")

    _load_local_api_key()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if client is None and not api_key:
        return _failed("OPENAI_API_KEY is not configured.")

    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    try:
        active_client = client or _create_openai_client(api_key)
        response = active_client.responses.parse(
            model=selected_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": USER_PROMPT},
                        {
                            "type": "input_image",
                            "image_url": _image_data_url(path),
                        },
                    ],
                },
            ],
            text_format=LabelExtraction,
        )
        return _parse_live_response(response.output_parsed)
    except Exception as error:  # The public function must not crash the UI.
        error_type = type(error).__name__
        return _failed(f"Vision API request failed ({error_type}).")
