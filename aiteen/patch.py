"""Deep-merge translated strings into locale JSON files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .audit import flatten, load_json, unflatten


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `overlay` into `base`. Returns a new dict."""
    result = {**base}
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def patch_locale(
    locales_dir: Path,
    locale: str,
    namespace_translations: dict[str, dict[str, str]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Apply translations to a single locale's JSON files.

    Returns a dict {namespace: count_of_keys_written}.
    """
    locale_dir = locales_dir / locale
    locale_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for ns, flat_translations in namespace_translations.items():
        if not flat_translations:
            continue
        ns_path = locale_dir / f"{ns}.json"
        existing: dict[str, Any] = {}
        if ns_path.is_file():
            existing = load_json(ns_path)

        # Convert existing to flat, override, then unflatten — preserves order
        # of source keys while letting us write nested dotted keys cleanly.
        flat_existing = flatten(existing)
        for key, val in flat_translations.items():
            flat_existing[key] = val
        merged = unflatten(flat_existing)
        # Deep-merge against the original existing dict to keep any keys
        # `flatten` may have collapsed (e.g. empty-dict leaves).
        merged = deep_merge(existing, merged)

        counts[ns] = len(flat_translations)
        if dry_run:
            continue
        with ns_path.open("w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2, sort_keys=False)
            fh.write("\n")
    return counts


def patch_all(
    locales_dir: Path,
    translations: dict[str, dict[str, dict[str, str]]],
    dry_run: bool = False,
) -> dict[str, dict[str, int]]:
    """Apply translations to every locale. Returns {locale: {ns: count}}."""
    return {
        locale: patch_locale(locales_dir, locale, ns_map, dry_run=dry_run)
        for locale, ns_map in translations.items()
    }
