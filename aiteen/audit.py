"""Audit locale files for missing translations.

Handles arbitrarily nested JSON. Compares each non-source locale against the
source locale (default: en). A key is considered "missing" if it's absent in
the target OR if its value equals the source value (i.e., untranslated).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict:
    """Load a JSON file, raising a clear error on malformed input."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in {path}: {e}") from e
    except OSError as e:
        raise OSError(f"Cannot read {path}: {e}") from e


def flatten(data: Any, parent: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dotted-key paths.

    Lists are treated as leaf values (translated as a whole). Non-string scalars
    are returned as-is so the caller can decide whether to translate them.
    """
    out: dict[str, Any] = {}
    if not isinstance(data, dict):
        return {parent: data} if parent else {}
    for key, value in data.items():
        path = f"{parent}.{key}" if parent else key
        if isinstance(value, dict):
            nested = flatten(value, path)
            if not nested:
                # Empty dict — preserve as leaf so deep-merge can recreate it.
                out[path] = {}
            else:
                out.update(nested)
        else:
            out[path] = value
    return out


def unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    """Inverse of flatten()."""
    result: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        cursor = result
        for part in parts[:-1]:
            existing = cursor.get(part)
            if not isinstance(existing, dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value
    return result


def list_namespaces(locale_dir: Path) -> list[str]:
    """Return the JSON file basenames (without .json) inside a locale directory."""
    if not locale_dir.is_dir():
        return []
    return sorted(p.stem for p in locale_dir.glob("*.json"))


def find_missing(
    source_dir: Path, target_dir: Path
) -> dict[str, dict[str, str]]:
    """Compare two locale dirs. Returns {namespace: {dotted_key: source_value}}.

    A key is missing if absent in the target, or if target value equals source
    value (untranslated leftover).
    """
    missing: dict[str, dict[str, str]] = {}
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source locale dir not found: {source_dir}")

    for ns in list_namespaces(source_dir):
        src_path = source_dir / f"{ns}.json"
        tgt_path = target_dir / f"{ns}.json"
        src = flatten(load_json(src_path))

        if not tgt_path.is_file():
            # Whole namespace missing — every translatable string is missing.
            ns_missing = {k: v for k, v in src.items() if isinstance(v, str)}
            if ns_missing:
                missing[ns] = ns_missing
            continue

        tgt = flatten(load_json(tgt_path))
        ns_missing: dict[str, str] = {}
        for key, src_val in src.items():
            if not isinstance(src_val, str):
                continue
            if key not in tgt:
                ns_missing[key] = src_val
            elif tgt[key] == src_val and src_val.strip():
                # Identical to source — likely untranslated.
                ns_missing[key] = src_val
        if ns_missing:
            missing[ns] = ns_missing
    return missing


def audit_all(
    locales_dir: Path, source_locale: str, target_locales: list[str]
) -> dict[str, dict[str, dict[str, str]]]:
    """Run the audit across every target locale.

    Returns: {locale: {namespace: {key: source_value}}}.
    """
    src_dir = locales_dir / source_locale
    report: dict[str, dict[str, dict[str, str]]] = {}
    for loc in target_locales:
        tgt_dir = locales_dir / loc
        report[loc] = find_missing(src_dir, tgt_dir)
    return report
