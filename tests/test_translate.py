"""Tests for aiteen.translate — OpenAI mocking, placeholder preservation."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aiteen.config import Config
from aiteen.translate import (
    build_prompt,
    extract_placeholders,
    translate_batch,
    translate_missing,
)


def _cfg(**kw) -> Config:
    defaults = dict(
        locales_dir=Path("/tmp/locales"),
        source_locale="en",
        target_locales=["de"],
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
    )
    defaults.update(kw)
    return Config(**defaults)


# ---------------------------------------------------------------------------
# extract_placeholders
# ---------------------------------------------------------------------------

class TestExtractPlaceholders:
    def test_curly_brace(self):
        assert extract_placeholders("Hello {name}") == ["{name}"]

    def test_double_curly_brace(self):
        assert extract_placeholders("{{escaped}}") == ["{{escaped}}"]

    def test_html_tag(self):
        assert extract_placeholders("<b>text</b>") == ["<b>", "</b>"]

    def test_multiple(self):
        result = extract_placeholders("{count} items <em>here</em>")
        assert "{count}" in result
        assert "<em>" in result

    def test_no_placeholders(self):
        assert extract_placeholders("plain text") == []

    def test_empty_string(self):
        assert extract_placeholders("") == []

    def test_percent_s(self):
        assert extract_placeholders("Hello %s") == ["%s"]


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_prompt_contains_source_text(self):
        cfg = _cfg()
        items = {"greeting": "Hello, World!"}
        messages = build_prompt(cfg, "de", "common", items)
        # User message must contain the source text
        user_content = messages[1]["content"]
        assert "Hello, World!" in user_content
        assert "greeting" in user_content

    def test_prompt_mentions_target_language(self):
        cfg = _cfg()
        messages = build_prompt(cfg, "de", "common", {"k": "v"})
        combined = " ".join(m["content"] for m in messages)
        assert "German" in combined

    def test_prompt_mentions_namespace(self):
        cfg = _cfg()
        messages = build_prompt(cfg, "de", "dashboard", {"k": "v"})
        combined = " ".join(m["content"] for m in messages)
        assert "dashboard" in combined

    def test_prompt_instructs_json_output(self):
        cfg = _cfg()
        messages = build_prompt(cfg, "de", "ns", {"k": "v"})
        combined = " ".join(m["content"] for m in messages)
        assert "JSON" in combined

    def test_nested_key_path_in_prompt(self):
        cfg = _cfg()
        items = {"ui.buttons.submit": "Submit"}
        messages = build_prompt(cfg, "de", "app", items)
        user_content = messages[1]["content"]
        assert "ui.buttons.submit" in user_content


# ---------------------------------------------------------------------------
# translate_batch — mocked completion_fn
# ---------------------------------------------------------------------------

class TestTranslateBatch:
    def _make_completion_fn(self, response: dict):
        def fn(messages, model):
            return json.dumps(response)
        return fn

    def test_basic_translation(self):
        cfg = _cfg()
        fn = self._make_completion_fn({"hello": "Hallo"})
        result = translate_batch(cfg, "de", "common", {"hello": "Hello"}, completion_fn=fn)
        assert result == {"hello": "Hallo"}

    def test_prompt_contains_source_text(self):
        """Captured messages must contain the source text."""
        cfg = _cfg()
        captured = []

        def fn(messages, model):
            captured.extend(messages)
            return json.dumps({"greeting": "Hallo"})

        translate_batch(cfg, "de", "ns", {"greeting": "Hello"}, completion_fn=fn)
        combined = " ".join(m["content"] for m in captured)
        assert "Hello" in combined

    def test_placeholder_curly_brace_preserved(self):
        """Translations that strip {count} should still be returned (QA checks later)."""
        cfg = _cfg()
        fn = self._make_completion_fn({"items": "{count} Artikel"})
        result = translate_batch(cfg, "de", "ns", {"items": "{count} items"}, completion_fn=fn)
        assert "{count}" in result["items"]

    def test_placeholder_html_tag_preserved(self):
        cfg = _cfg()
        fn = self._make_completion_fn({"label": "<b>Fett</b> Text"})
        result = translate_batch(cfg, "de", "ns", {"label": "<b>Bold</b> text"}, completion_fn=fn)
        assert "<b>" in result["label"]

    def test_nested_key_paths_handled(self):
        cfg = _cfg()
        items = {"ui.header.title": "Dashboard", "ui.header.subtitle": "Overview"}
        fn = self._make_completion_fn({
            "ui.header.title": "Übersicht",
            "ui.header.subtitle": "Zusammenfassung",
        })
        result = translate_batch(cfg, "de", "app", items, completion_fn=fn)
        assert result["ui.header.title"] == "Übersicht"
        assert result["ui.header.subtitle"] == "Zusammenfassung"

    def test_empty_items_returns_empty(self):
        cfg = _cfg()
        result = translate_batch(cfg, "de", "ns", {}, completion_fn=lambda m, mo: "{}")
        assert result == {}

    def test_retries_on_invalid_json(self):
        cfg = _cfg(max_retries=3)
        call_count = [0]

        def fn(messages, model):
            call_count[0] += 1
            if call_count[0] < 3:
                return "not json"
            return json.dumps({"k": "v"})

        result = translate_batch(cfg, "de", "ns", {"k": "value"}, completion_fn=fn)
        assert result == {"k": "v"}
        assert call_count[0] == 3

    def test_raises_after_max_retries(self):
        cfg = _cfg(max_retries=2)

        def fn(messages, model):
            return "INVALID JSON"

        with pytest.raises(RuntimeError, match="Failed to parse"):
            translate_batch(cfg, "de", "ns", {"k": "v"}, completion_fn=fn)

    def test_missing_api_key_raises_clear_error(self):
        """No stack trace — clear RuntimeError with guidance."""
        cfg = _cfg(openai_api_key=None)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            # No completion_fn → will try to create OpenAI client → require_api_key
            translate_batch(cfg, "de", "ns", {"k": "v"})

    def test_model_returns_non_dict_raises(self):
        cfg = _cfg(max_retries=1)

        def fn(messages, model):
            return '["not", "a", "dict"]'

        with pytest.raises(RuntimeError):
            translate_batch(cfg, "de", "ns", {"k": "v"}, completion_fn=fn)

    def test_keys_not_in_response_skipped_gracefully(self):
        cfg = _cfg()
        # Model only returns one of two requested keys
        fn = self._make_completion_fn({"a": "A translated"})
        result = translate_batch(cfg, "de", "ns", {"a": "A", "b": "B"}, completion_fn=fn)
        assert "a" in result
        assert "b" not in result  # silently skipped


# ---------------------------------------------------------------------------
# translate_missing
# ---------------------------------------------------------------------------

class TestTranslateMissing:
    def test_full_pipeline_mocked(self):
        cfg = _cfg()

        def fn(messages, model):
            # Reflect back a "translated" version of whatever was asked
            user = messages[1]["content"]
            # Parse the JSON block from the user message
            start = user.index("```json\n") + 8
            end = user.index("\n```", start)
            data = json.loads(user[start:end])
            return json.dumps({k: f"[de] {v}" for k, v in data.items()})

        audit_report = {
            "de": {
                "common": {"hello": "Hello", "world": "World"},
            }
        }
        result = translate_missing(cfg, audit_report, completion_fn=fn)
        assert "de" in result
        assert "common" in result["de"]
        assert result["de"]["common"]["hello"] == "[de] Hello"
        assert result["de"]["common"]["world"] == "[de] World"

    def test_empty_audit_report_returns_empty(self):
        cfg = _cfg()
        result = translate_missing(cfg, {}, completion_fn=lambda m, mo: "{}")
        assert result == {}
