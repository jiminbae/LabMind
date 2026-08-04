"""Optional Gemini-to-SMARTS query translation with no inventory authority."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .classification_service import CHEMICAL_LABEL_OPTIONS
from .provider_config import DEFAULT_ENV_PATH, resolve_gemini_config
from .provider_errors import provider_failure_message
from .safety_rules import STORAGE_CONSTRAINT_OPTIONS


MAX_QUESTION_LENGTH = 600
MAX_SMARTS_PATTERNS = 3

QUERY_PROMPT = """Translate one laboratory chemistry question into a constrained
structure-search plan. Return JSON only with:

- concept: a short chemistry concept name.
- patterns: one to three RDKit SMARTS strings.
- required_labels: zero or more values only from the supplied chemical label
  list. Use labels only when they are required to avoid an overly broad match.
- explanation: short explanation of the intended structural criterion.

Do not answer whether a reagent is in stock. Do not create SQL. Do not choose a
storage location. Do not give a synthesis recommendation. If a safe structure
criterion cannot be expressed, return an empty patterns list.

Allowed chemical labels: {chemical_labels}
Allowed storage constraints (not valid required_labels): {storage_constraints}
"""


class ChemicalQueryTranslation(BaseModel):
    concept: str = "Chemical structure query"
    patterns: list[str] = Field(default_factory=list, max_length=MAX_SMARTS_PATTERNS)
    required_labels: list[str] = Field(default_factory=list)
    explanation: str = ""


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


def _response_to_model(response: Any) -> ChemicalQueryTranslation:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ChemicalQueryTranslation):
        return parsed
    if isinstance(parsed, dict):
        return ChemicalQueryTranslation.model_validate(parsed)
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("The query provider returned no structured result.")
    return ChemicalQueryTranslation.model_validate(json.loads(text))


def _safe_strings(values: list[str], allowed: frozenset[str]) -> list[str]:
    accepted: list[str] = []
    for value in values:
        normalized = value.strip() if isinstance(value, str) else ""
        if normalized in allowed and normalized not in accepted:
            accepted.append(normalized)
    return accepted


def translate_chemical_question(
    question: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_path=DEFAULT_ENV_PATH,
    client: Any | None = None,
) -> QueryTranslationResult:
    """Return a model-generated query *plan*, never an availability answer."""

    normalized_question = question.strip()
    if not normalized_question:
        return QueryTranslationResult("failed", None, "Enter a chemistry question.")
    if len(normalized_question) > MAX_QUESTION_LENGTH:
        return QueryTranslationResult(
            "failed",
            None,
            f"Keep chemistry questions under {MAX_QUESTION_LENGTH} characters.",
        )

    try:
        config = resolve_gemini_config(environ=environ, env_path=env_path)
    except ValueError as error:
        return QueryTranslationResult("failed", None, str(error))
    if config.mode != "live" or not config.api_key:
        return QueryTranslationResult(
            "manual",
            None,
            "No live chemistry translator is configured for this question.",
        )

    prompt = (
        QUERY_PROMPT.format(
            chemical_labels=", ".join(sorted(CHEMICAL_LABEL_OPTIONS)),
            storage_constraints=", ".join(STORAGE_CONSTRAINT_OPTIONS),
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
                    "response_schema": ChemicalQueryTranslation,
                },
            )
        else:
            response = active_client.models.generate_content(
                model=config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ChemicalQueryTranslation,
                ),
            )
        parsed = _response_to_model(response)
    except Exception as error:  # Do not surface raw provider internals or crash search.
        return QueryTranslationResult(
            "failed",
            None,
            provider_failure_message(
                error,
                operation="Chemistry translation",
                fallback="No inventory answer was generated.",
            ),
        )

    patterns = [
        pattern.strip()
        for pattern in parsed.patterns
        if isinstance(pattern, str) and pattern.strip()
    ][:MAX_SMARTS_PATTERNS]
    labels = _safe_strings(parsed.required_labels, CHEMICAL_LABEL_OPTIONS)
    if not patterns:
        return QueryTranslationResult(
            "manual",
            None,
            "The translator did not return a safe SMARTS plan; no inventory answer was generated.",
        )
    return QueryTranslationResult(
        "success",
        {
            "concept": parsed.concept.strip() or "Chemical structure query",
            "patterns": patterns,
            "required_labels": labels,
            "explanation": (
                parsed.explanation.strip()
                or "Model-proposed SMARTS will be validated before inventory matching."
            ),
        },
        "A chemistry search plan was proposed. RDKit validation still decides whether it runs.",
    )
