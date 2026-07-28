"""Optional Gemini chemistry labeling with a CAS-level safety cache.

The service can describe allowed function labels and storage constraints.  It
cannot return a cabinet/location; :mod:`backend.safety_rules` remains the only
place that makes that deterministic recommendation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .cas_validator import validate_cas_details
from .classification_cache import get_cas_classification, upsert_cas_classification
from .provider_config import DEFAULT_ENV_PATH, resolve_gemini_config
from .safety_rules import STORAGE_CONSTRAINT_OPTIONS


CHEMICAL_LABEL_OPTIONS = frozenset(
    {
        "Brønsted acid",
        "Chiral ligand",
        "Flammable liquid",
        "Inorganic compound",
        "Lewis acid",
        "Moisture reactive",
        "Organic compound",
        "Organometallic",
        "Organophosphorus compound",
        "Phosphine ligand",
        "Protic solvent",
        "Pyrophoric",
        "Reducing agent",
    }
)


CLASSIFICATION_PROMPT = """Classify this laboratory reagent using chemical
knowledge only. Return JSON with:

- labels: zero or more values only from the allowed chemical-function labels.
- constraints: zero or more values only from the allowed storage constraints.
- confidence: a number from 0 to 1.
- rationale: a short explanation of the chemistry labels and constraints.

Important safety boundary: never choose a cabinet, shelf, room, or final
storage location. Do not invent a CAS number or identity. If identity is too
uncertain, return empty label and constraint lists with a low confidence.
"""


class ChemicalClassification(BaseModel):
    labels: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    status: str
    classification: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _manual_result(cas_number: str, message: str) -> ClassificationResult:
    return ClassificationResult(
        status="manual",
        classification={
            "cas_number": cas_number,
            "labels": [],
            "constraints": [],
            "confidence": 0.0,
            "rationale": "A chemistry reviewer must classify this material.",
            "cache_status": "Manual classification required",
        },
        message=message,
    )


def _cached_result(cached: Mapping[str, Any]) -> ClassificationResult:
    return ClassificationResult(
        status="cached",
        classification={
            "cas_number": cached["cas_number"],
            "labels": list(cached["chemical_tags"]),
            "constraints": list(cached["hazard_labels"]),
            "confidence": float(cached.get("confidence") or 0),
            "rationale": cached.get("rationale") or "CAS classification cache.",
            "cache_status": (
                "Reviewer-confirmed CAS cache"
                if cached.get("reviewed")
                else "CAS classification cache"
            ),
        },
        message="A cached CAS classification was reused; no model call was made.",
    )


def _create_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "The google-genai package is not installed. Install requirements.txt."
        ) from error
    return genai.Client(api_key=api_key)


def _response_to_model(response: Any) -> ChemicalClassification:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ChemicalClassification):
        return parsed
    if isinstance(parsed, dict):
        return ChemicalClassification.model_validate(parsed)
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("The classification provider returned no structured result.")
    return ChemicalClassification.model_validate(json.loads(text))


def _validated_values(values: list[str], allowed: frozenset[str]) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []
    for value in values:
        normalized = value.strip() if isinstance(value, str) else ""
        if normalized in allowed and normalized not in accepted:
            accepted.append(normalized)
        elif normalized:
            rejected.append(normalized)
    return accepted, rejected


def classify_cas_with_gemini(
    cas_number: object,
    *,
    chemical_name: str | None = None,
    db_path: str | None = None,
    environ: Mapping[str, str] | None = None,
    env_path=DEFAULT_ENV_PATH,
    client: Any | None = None,
    force: bool = False,
) -> ClassificationResult:
    """Classify a valid CAS once, cache the allowed labels, and fail closed."""

    cas_result = validate_cas_details(cas_number)
    if not cas_result.is_valid or cas_result.normalized_cas is None:
        return _manual_result("", cas_result.error_message or "CAS number is invalid.")
    normalized_cas = cas_result.normalized_cas

    cached = get_cas_classification(normalized_cas, db_path)
    if cached and not force:
        return _cached_result(cached)

    try:
        config = resolve_gemini_config(environ=environ, env_path=env_path)
    except ValueError as error:
        return _manual_result(normalized_cas, str(error))
    if config.mode != "live":
        return _manual_result(
            normalized_cas,
            "AI classification is not configured. Review labels and constraints manually.",
        )
    if not config.api_key:
        return _manual_result(
            normalized_cas,
            "AI classification is enabled, but GEMINI_API_KEY is not configured.",
        )

    prompt = (
        f"{CLASSIFICATION_PROMPT}\n\nCAS number: {normalized_cas}\n"
        f"Chemical name from the reviewed label: {(chemical_name or '').strip() or 'Not supplied'}"
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
                    "response_schema": ChemicalClassification,
                },
            )
        else:
            response = active_client.models.generate_content(
                model=config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ChemicalClassification,
                ),
            )
        parsed = _response_to_model(response)
    except Exception as error:  # Provider details must not crash or leak to the UI.
        return _manual_result(
            normalized_cas,
            "AI classification could not complete. Review labels and constraints manually "
            f"({type(error).__name__}).",
        )

    labels, rejected_labels = _validated_values(parsed.labels, CHEMICAL_LABEL_OPTIONS)
    constraints, rejected_constraints = _validated_values(
        parsed.constraints,
        frozenset(STORAGE_CONSTRAINT_OPTIONS),
    )
    rejected = rejected_labels + rejected_constraints
    rationale = parsed.rationale.strip() or "No rationale was supplied."
    if rejected:
        rationale += " Unsupported model labels were discarded."

    cached = upsert_cas_classification(
        normalized_cas,
        chemical_tags=labels,
        hazard_labels=constraints,
        confidence=float(parsed.confidence),
        source="Gemini chemical classification",
        rationale=rationale,
        reviewed=False,
        db_path=db_path,
    )
    result = _cached_result(cached)
    return ClassificationResult(
        status="success" if labels or constraints else "manual",
        classification=result.classification,
        message=(
            "AI classification is ready for review. The deterministic rule engine "
            "will determine storage."
            if labels or constraints
            else "The model did not return an approved chemistry label. Review manually."
        ),
    )
