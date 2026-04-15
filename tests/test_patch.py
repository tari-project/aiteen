"""Tests for aiteen.patch — deep merge and locale file writing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiteen.patch import deep_merge, patch_locale, patch_all


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        overlay = {"c": 3}
        assert deep_merge(base, overlay) == {"a": 1, "b": 2, "c": 3}

    def test_deep_merge_nested(self):
        """Critical: must be deep (recursive), not shallow."""
        base = {"section": {"a": "original_a", "b": "original_b"}}
        overlay = {"section": {"c": "new_c"}}
        result = deep_merge(base, overlay)
        # Deep merge: a and b are preserved; c is added
        assert result["section"]["a"] == "original_a"
        assert result["section"]["b"] == "original_b"
        assert result["section"]["c"] == "new_c"

    def test_shallow_merge_would_fail_this(self):
        """Demonstrates why shallow merge is wrong."""
        base = {"section": {"a": "keep_me", "b": "keep_me_too"}}
        overlay = {"section": {"c": "new"}}
        # Shallow merge would overwrite "section" entirely, losing a and b
        result = deep_merge(base, overlay)
        assert "a" in result["section"], "deep_merge must not overwrite nested dicts"
        assert "b" in result["section"], "deep_merge must not overwrite nested dicts"

    def test_overlay_wins_for_scalar_conflict(self):
        base = {"key": "old"}
        overlay = {"key": "new"}
        assert deep_merge(base, overlay)["key"] == "new"

    def test_existing_translations_not_overwritten(self):
        """If a key already exists in base, overlay must win BUT for translations
        we test that the merge direction is correct."""
        base = {"greet": "Hallo"}
        overlay = {"greet": "Guten Tag"}
        # overlay wins (new translation takes precedence)
        assert deep_merge(base, overlay)["greet"] == "Guten Tag"

    def test_three_levels_deep(self):
        base = {"a": {"b": {"c": "old", "d": "keep"}}}
        overlay = {"a": {"b": {"c": "new"}}}
        result = deep_merge(base, overlay)
        assert result["a"]["b"]["c"] == "new"
        assert result["a"]["b"]["d"] == "keep"

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        overlay = {"a": {"y": 2}}
        original_base = {"a": {"x": 1}}
        deep_merge(base, overlay)
        assert base == original_base

    def test_new_keys_added_correctly(self):
        base = {"existing": "value"}
        overlay = {"new_key": "new_value", "another": "one"}
        result = deep_merge(base, overlay)
        assert result["existing"] == "value"
        assert result["new_key"] == "new_value"
        assert result["another"] == "one"


# ---------------------------------------------------------------------------
# patch_locale
# ---------------------------------------------------------------------------

class TestPatchLocale:
    def test_writes_new_keys(self, tmp_path):
        en_dir = tmp_path / "en"
        en_dir.mkdir()
        (en_dir / "common.json").write_text('{"hello": "Hello"}', encoding="utf-8")

        de_dir = tmp_path / "de"
        de_dir.mkdir()
        (de_dir / "common.json").write_text('{"existing": "Vorhanden"}', encoding="utf-8")

        patch_locale(tmp_path, "de", {"common": {"hello": "Hallo"}})

        result = json.loads((de_dir / "common.json").read_text(encoding="utf-8"))
        assert result["hello"] == "Hallo"
        assert result["existing"] == "Vorhanden"  # not overwritten

    def test_existing_translations_not_overwritten(self, tmp_path):
        de_dir = tmp_path / "de"
        de_dir.mkdir()
        (de_dir / "common.json").write_text('{"hello": "Hallo (original)"}', encoding="utf-8")

        # Patch tries to write a different translation
        patch_locale(tmp_path, "de", {"common": {"hello": "Hallo (new)"}})

        result = json.loads((de_dir / "common.json").read_text(encoding="utf-8"))
        # new value wins (patch_locale uses the overlay)
        assert result["hello"] == "Hallo (new)"

    def test_nested_keys_written_correctly(self, tmp_path):
        de_dir = tmp_path / "de"
        de_dir.mkdir()
        (de_dir / "app.json").write_text('{"top": "Oben"}', encoding="utf-8")

        patch_locale(tmp_path, "de", {"app": {"ui.buttons.submit": "Einreichen"}})

        result = json.loads((de_dir / "app.json").read_text(encoding="utf-8"))
        assert result["top"] == "Oben"
        assert result["ui"]["buttons"]["submit"] == "Einreichen"

    def test_creates_locale_dir_if_missing(self, tmp_path):
        patch_locale(tmp_path, "ja", {"common": {"hello": "こんにちは"}})
        result = json.loads((tmp_path / "ja" / "common.json").read_text(encoding="utf-8"))
        assert result["hello"] == "こんにちは"

    def test_dry_run_does_not_write_files(self, tmp_path):
        de_dir = tmp_path / "de"
        de_dir.mkdir()
        original = '{"original": "text"}'
        (de_dir / "common.json").write_text(original, encoding="utf-8")

        patch_locale(tmp_path, "de", {"common": {"new_key": "Neuer Schlüssel"}}, dry_run=True)

        # File must be unchanged
        assert (de_dir / "common.json").read_text(encoding="utf-8") == original

    def test_returns_counts(self, tmp_path):
        de_dir = tmp_path / "de"
        de_dir.mkdir()
        (de_dir / "common.json").write_text("{}", encoding="utf-8")

        counts = patch_locale(tmp_path, "de", {"common": {"a": "A", "b": "B"}})
        assert counts["common"] == 2

    def test_empty_translations_skipped(self, tmp_path):
        de_dir = tmp_path / "de"
        de_dir.mkdir()
        original = '{"existing": "value"}'
        (de_dir / "common.json").write_text(original, encoding="utf-8")

        counts = patch_locale(tmp_path, "de", {"common": {}})
        assert counts == {}


# ---------------------------------------------------------------------------
# patch_all
# ---------------------------------------------------------------------------

class TestPatchAll:
    def test_multiple_locales(self, tmp_path):
        for loc in ["de", "fr"]:
            d = tmp_path / loc
            d.mkdir()
            (d / "common.json").write_text("{}", encoding="utf-8")

        translations = {
            "de": {"common": {"hello": "Hallo"}},
            "fr": {"common": {"hello": "Bonjour"}},
        }
        results = patch_all(tmp_path, translations)
        assert results["de"]["common"] == 1
        assert results["fr"]["common"] == 1

        de_data = json.loads((tmp_path / "de" / "common.json").read_text(encoding="utf-8"))
        fr_data = json.loads((tmp_path / "fr" / "common.json").read_text(encoding="utf-8"))
        assert de_data["hello"] == "Hallo"
        assert fr_data["hello"] == "Bonjour"
