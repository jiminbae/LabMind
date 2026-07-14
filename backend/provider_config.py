"""Provider-specific configuration for LabMind vision requests."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"
OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_UNIVIBE_BASE_URL = "https://api.univibe.cc/openai/v1"

ALLOWED_ENV_NAMES = {
    "LABMIND_PROVIDER",
    "LABMIND_VISION_MODE",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "UNIVIBE_API_KEY",
    "UNIVIBE_BASE_URL",
    "UNIVIBE_MODEL",
}


@dataclass(frozen=True, slots=True)
class VisionProviderConfig:
    name: str
    api_key: str | None = field(repr=False)
    base_url: str
    model: str
    chat_completions_fallback: bool = False


def _read_env_file(env_path: Path | None) -> dict[str, str]:
    if env_path is None or not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    with env_path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in ALLOWED_ENV_NAMES:
                continue
            values[key] = value.strip().strip('"').strip("'")
    return values


def _merged_environment(
    environ: Mapping[str, str] | None,
    env_path: Path | None,
) -> dict[str, str]:
    values = _read_env_file(env_path)
    values.update(dict(os.environ if environ is None else environ))
    return values


def _validated_univibe_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise ValueError("UNIVIBE_BASE_URL must use HTTPS.")
    if parsed.hostname != "api.univibe.cc":
        raise ValueError("UNIVIBE_BASE_URL must use the api.univibe.cc host.")
    if not parsed.path.endswith("/openai/v1"):
        raise ValueError("UNIVIBE_BASE_URL must end with /openai/v1.")
    return base_url


def resolve_provider_config(
    provider: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
) -> VisionProviderConfig:
    """Resolve one provider without ever mixing provider credentials."""

    values = _merged_environment(environ, env_path)
    selected = (provider or values.get("LABMIND_PROVIDER") or "openai").lower()

    if selected == "openai":
        return VisionProviderConfig(
            name="openai",
            api_key=values.get("OPENAI_API_KEY") or None,
            # Explicitly pin the official endpoint so OPENAI_BASE_URL cannot
            # redirect the official key to an unrelated host.
            base_url=OFFICIAL_OPENAI_BASE_URL,
            model=values.get("OPENAI_MODEL") or "gpt-4o",
        )

    if selected == "univibe":
        return VisionProviderConfig(
            name="univibe",
            api_key=values.get("UNIVIBE_API_KEY") or None,
            base_url=_validated_univibe_base_url(
                values.get("UNIVIBE_BASE_URL") or DEFAULT_UNIVIBE_BASE_URL
            ),
            model=values.get("UNIVIBE_MODEL") or "gpt-5.4",
            chat_completions_fallback=True,
        )

    raise ValueError("LABMIND_PROVIDER must be 'openai' or 'univibe'.")
