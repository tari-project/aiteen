"""Configuration loading: dotenv + YAML + CLI overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


# Map of locale codes to full language names. Used in translation prompts.
LOCALE_LANGUAGE_MAP = {
    "en": "English",
    "af": "Afrikaans",
    "ar": "Arabic",
    "cn": "Chinese (Simplified)",
    "zh": "Chinese (Simplified)",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "es": "Spanish",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
}


@dataclass
class Config:
    """Aiteen runtime configuration."""

    locales_dir: Path
    source_locale: str = "en"
    target_locales: list[str] = field(default_factory=list)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    project_context: str = (
        "Tari is an open-source decentralized blockchain protocol. "
        "The strings come from a wallet/mining UI."
    )
    batch_size: int = 25
    max_retries: int = 3
    dry_run: bool = False

    @classmethod
    def load(
        cls,
        locales_dir: str | Path,
        config_file: Optional[str | Path] = None,
        **overrides,
    ) -> "Config":
        """Load configuration: defaults < .env < YAML file < CLI overrides."""
        load_dotenv()

        data: dict = {
            "locales_dir": Path(locales_dir),
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        }
        if os.environ.get("OPENAI_MODEL"):
            data["openai_model"] = os.environ["OPENAI_MODEL"]

        if config_file:
            cfg_path = Path(config_file)
            if not cfg_path.is_file():
                raise FileNotFoundError(f"Config file not found: {cfg_path}")
            with cfg_path.open("r", encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}
            for k, v in yaml_data.items():
                if k == "locales_dir" and v:
                    # Resolve relative to config file's parent
                    p = Path(v)
                    if not p.is_absolute():
                        p = (cfg_path.parent / p).resolve()
                    data["locales_dir"] = p
                else:
                    data[k] = v

        for k, v in overrides.items():
            if v is not None:
                data[k] = v

        # Auto-detect target locales from locales_dir if not set
        if not data.get("target_locales"):
            data["target_locales"] = cls._detect_locales(
                data["locales_dir"], data.get("source_locale", "en")
            )

        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    @staticmethod
    def _detect_locales(locales_dir: Path, source: str) -> list[str]:
        if not locales_dir.is_dir():
            return []
        return sorted(
            p.name
            for p in locales_dir.iterdir()
            if p.is_dir() and p.name != source and not p.name.startswith(".")
        )

    def language_name(self, locale: str) -> str:
        """Get the human-readable language name for a locale code."""
        return LOCALE_LANGUAGE_MAP.get(locale, locale)

    def require_api_key(self) -> str:
        """Return the OpenAI API key or raise a clear error."""
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Provide it via environment variable, "
                ".env file, or --openai-api-key flag."
            )
        return self.openai_api_key
