"""Translate missing strings via OpenAI ChatCompletion.

Context-aware: passes neighbouring keys, the namespace name, and the project
description so the model produces idiomatic translations. Preserves
placeholders ({var}, {{var}}, %s, <tag>...</tag>) verbatim.
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

from .config import Config

PLACEHOLDER_RE = re.compile(
    r"(\{\{[^}]+\}\}|\{[^}]+\}|%\([^)]+\)[sdif]|%[sdif]|<[^>]+>)"
)


def extract_placeholders(text: str) -> list[str]:
    """Return ordered list of placeholders found in text."""
    return PLACEHOLDER_RE.findall(text or "")


def build_prompt(
    cfg: Config,
    locale: str,
    namespace: str,
    items: dict[str, str],
) -> list[dict]:
    """Build the chat messages for a translation batch."""
    target_lang = cfg.language_name(locale)
    source_lang = cfg.language_name(cfg.source_locale)

    system = (
        f"You are a professional localization engineer translating {source_lang} "
        f"strings into {target_lang} for a software UI.\n\n"
        f"PROJECT CONTEXT:\n{cfg.project_context}\n\n"
        f"NAMESPACE: '{namespace}' — strings on this screen are thematically related.\n\n"
        "RULES:\n"
        "1. Preserve every placeholder exactly: {var}, {{var}}, %s, %d, %(name)s, "
        "<b>...</b>, <0>...</0>, etc. Do not translate text inside placeholders.\n"
        "2. Preserve leading/trailing whitespace and punctuation style.\n"
        "3. Keep the translated length reasonable for UI (no rambling).\n"
        "4. Do not add quotes, explanations, or commentary.\n"
        "5. Return STRICT JSON: an object mapping each input key to its translation.\n"
        "6. Translate every key. Never omit any.\n"
    )

    # Show keys with their source values; key paths give hierarchical context.
    payload = {k: v for k, v in items.items()}
    user = (
        f"Translate the values below into {target_lang}. "
        f"Keys are dotted paths showing UI hierarchy — use them as context.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Return ONLY a JSON object with the same keys and translated values."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _chunks(items: dict[str, str], size: int):
    keys = list(items.keys())
    for i in range(0, len(keys), size):
        chunk_keys = keys[i : i + size]
        yield {k: items[k] for k in chunk_keys}


def translate_batch(
    cfg: Config,
    locale: str,
    namespace: str,
    items: dict[str, str],
    client: Optional[object] = None,
    completion_fn: Optional[Callable] = None,
) -> dict[str, str]:
    """Translate one batch of strings. Returns {key: translation}.

    `completion_fn` is injected for testing — it should accept (messages, model)
    and return a JSON string (the assistant's response content).
    """
    if not items:
        return {}

    if completion_fn is None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.require_api_key())

        def completion_fn(messages, model):
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content

    out: dict[str, str] = {}
    for chunk in _chunks(items, cfg.batch_size):
        messages = build_prompt(cfg, locale, namespace, chunk)
        last_err: Optional[Exception] = None
        for attempt in range(1, cfg.max_retries + 1):
            try:
                content = completion_fn(messages, cfg.openai_model)
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("Model did not return a JSON object")
                # Only keep keys we asked for.
                for k in chunk:
                    if k in parsed and isinstance(parsed[k], str):
                        out[k] = parsed[k]
                break
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
                if attempt == cfg.max_retries:
                    raise RuntimeError(
                        f"Failed to parse model output for {locale}/{namespace}: {e}"
                    ) from e
                time.sleep(0.5 * attempt)
            except Exception as e:  # network / API errors
                last_err = e
                if attempt == cfg.max_retries:
                    raise
                time.sleep(1.0 * attempt)
    return out


def translate_missing(
    cfg: Config,
    audit_report: dict[str, dict[str, dict[str, str]]],
    completion_fn: Optional[Callable] = None,
) -> dict[str, dict[str, dict[str, str]]]:
    """Translate every missing string in an audit report.

    Returns the same shape as the audit report but with translated values.
    """
    translated: dict[str, dict[str, dict[str, str]]] = {}
    client = None
    if completion_fn is None and any(
        any(items for items in ns.values()) for ns in audit_report.values()
    ):
        from openai import OpenAI

        client = OpenAI(api_key=cfg.require_api_key())

    for locale, namespaces in audit_report.items():
        translated[locale] = {}
        for namespace, items in namespaces.items():
            if not items:
                continue
            translated[locale][namespace] = translate_batch(
                cfg, locale, namespace, items, client=client, completion_fn=completion_fn
            )
    return translated
