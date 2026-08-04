"""Configuration helpers for optional LabMind AI providers.

The application intentionally defaults to manual entry.  A provider is used
only when an operator explicitly configures live mode and supplies a key
through Streamlit secrets or a local ``.env.local`` file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"

PROVIDER_ENV_NAMES = frozenset(
    {
        "LABMIND_VISION_MODE",
        "LABMIND_PROVIDER",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
    }
)


@dataclass(frozen=True, slots=True)
class GeminiProviderConfig:
    """The small, explicit configuration surface for Gemini calls."""

    mode: str
    provider: str
    api_key: str | None = field(repr=False)
    model: str


def _read_env_file(env_path: Path | None) -> dict[str, str]:
    """Read only known configuration names from a local, ignored env file."""

    if env_path is None or not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in PROVIDER_ENV_NAMES:
            values[key] = value.strip().strip('"').strip("'")
    return values


def load_provider_environment(
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
) -> dict[str, str]:
    """Load allowed settings, with explicit/process values taking precedence."""

    values = _read_env_file(env_path)
    raw_environment = os.environ if environ is None else environ
    values.update(
        {
            key: value
            for key, value in raw_environment.items()
            if key in PROVIDER_ENV_NAMES and isinstance(value, str)
        }
    )
    return values


def resolve_gemini_config(
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
) -> GeminiProviderConfig:
    """Resolve one opt-in Gemini configuration without exposing its key."""

    values = load_provider_environment(environ, env_path)
    mode = (values.get("LABMIND_VISION_MODE") or "manual").strip().lower()
    provider = (values.get("LABMIND_PROVIDER") or "gemini").strip().lower()

    if mode not in {"manual", "live"}:
        raise ValueError("LABMIND_VISION_MODE must be 'manual' or 'live'.")
    if provider not in {"gemini", "google"}:
        raise ValueError("LABMIND_PROVIDER must be 'gemini' when live mode is used.")

    gemini_key = values.get("GEMINI_API_KEY", "").strip()
    google_key = values.get("GOOGLE_API_KEY", "").strip()
    if mode == "live" and gemini_key and google_key and gemini_key != google_key:
        raise ValueError(
            "GEMINI_API_KEY and GOOGLE_API_KEY contain different values. "
            "Remove the old GOOGLE_API_KEY and keep GEMINI_API_KEY only."
        )
    model = values.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

    return GeminiProviderConfig(
        mode=mode,
        provider="gemini",
        api_key=gemini_key or google_key or None,
        model=model,
    )
