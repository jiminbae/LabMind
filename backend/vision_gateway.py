"""Provider-aware entry point for LabMind label extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .provider_config import (
    DEFAULT_ENV_PATH,
    VisionProviderConfig,
    load_provider_environment,
    resolve_provider_config,
)
from .schemas import OCRResult, ResultStatus
from .vision_service import (
    LabelExtraction,
    SYSTEM_PROMPT,
    USER_PROMPT,
    _failed,
    _image_data_url,
    _parse_live_response,
    _validate_image_path,
    extract_label_info as extract_with_responses,
)


def _create_client(config: VisionProviderConfig) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def _should_try_chat_fallback(result: OCRResult) -> bool:
    return bool(
        result.status is ResultStatus.FAILED
        and result.error_message
        and result.error_message.startswith("Vision API request failed")
    )


def _extract_with_chat_completions(
    image_path: str | Path,
    *,
    model: str,
    client: Any,
) -> OCRResult:
    """Compatibility fallback for relays without the Responses endpoint shape."""

    try:
        path = _validate_image_path(image_path)
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(path)},
                        },
                    ],
                },
            ],
            response_format=LabelExtraction,
        )
        parsed = completion.choices[0].message.parsed
        return _parse_live_response(parsed)
    except Exception as error:
        return _failed(
            "UniVibe request failed through both Responses API and "
            f"Chat Completions ({type(error).__name__})."
        )


def extract_label_with_provider(
    image_path: str | Path,
    *,
    mode: str | None = None,
    provider: str | None = None,
    client: Any | None = None,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
) -> OCRResult:
    """Extract a label using mock, official OpenAI, or UniVibe mode."""

    environment = load_provider_environment(environ, env_path)
    selected_mode = (mode or environment.get("LABMIND_VISION_MODE") or "mock").lower()
    if selected_mode == "mock":
        return extract_with_responses(image_path, mode="mock")
    if selected_mode != "live":
        return _failed("LABMIND_VISION_MODE must be 'mock' or 'live'.")

    try:
        config = resolve_provider_config(
            provider,
            environ=environment,
            env_path=env_path,
        )
    except ValueError as error:
        return _failed(str(error))

    if not config.api_key:
        variable = "OPENAI_API_KEY" if config.name == "openai" else "UNIVIBE_API_KEY"
        return _failed(f"{variable} is not configured.")

    try:
        active_client = client or _create_client(config)
    except Exception as error:
        return _failed(f"Could not initialize {config.name} client ({type(error).__name__}).")

    result = extract_with_responses(
        image_path,
        mode="live",
        model=config.model,
        client=active_client,
    )

    if config.chat_completions_fallback and _should_try_chat_fallback(result):
        return _extract_with_chat_completions(
            image_path,
            model=config.model,
            client=active_client,
        )
    return result
