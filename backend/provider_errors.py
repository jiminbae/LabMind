"""Turn provider exceptions into useful, secret-safe operator messages."""

from __future__ import annotations

from typing import Any


_ERROR_GUIDANCE = {
    400: (
        "INVALID_ARGUMENT",
        "Gemini rejected the request. Check the configured model and request format.",
    ),
    401: (
        "UNAUTHENTICATED",
        "The Gemini API key is invalid or has been revoked.",
    ),
    403: (
        "PERMISSION_DENIED",
        "The Gemini API key or project does not have permission for this request.",
    ),
    404: (
        "NOT_FOUND",
        "The configured Gemini model is not available to this project.",
    ),
    429: (
        "RESOURCE_EXHAUSTED",
        "The Gemini quota or rate limit was reached.",
    ),
}


def _http_code(error: Exception) -> int | None:
    """Read a numeric status without including the provider's raw response."""

    for attribute in ("code", "status_code"):
        value: Any = getattr(error, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def provider_failure_message(
    error: Exception,
    *,
    operation: str,
    fallback: str,
) -> str:
    """Describe a provider failure without exposing its response, request, or key."""

    code = _http_code(error)
    if code in _ERROR_GUIDANCE:
        status, guidance = _ERROR_GUIDANCE[code]
        identifier = f"{code} {status}"
    elif code is not None and 500 <= code <= 599:
        identifier = f"{code} SERVER_ERROR"
        guidance = "Gemini is temporarily unavailable."
    elif code is not None:
        identifier = str(code)
        guidance = "Gemini returned an unexpected response."
    else:
        identifier = type(error).__name__
        guidance = "The provider returned an unreadable or unexpected response."

    return f"{operation} could not complete ({identifier}). {guidance} {fallback}"
