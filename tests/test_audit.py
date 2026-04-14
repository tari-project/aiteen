"""Tests for aiteen.audit — missing-key detection with nested support."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from aiteen.audit import audit_all, find_missing, flatten, unflatten


# ---------------------------------------------------------------------------
# flatten / unflatten helpers
# ---------------------------------------------------------------------------

class TestFlatten:
    def test_flat_dict(self):
        assert flatten({"a": "1", "b": "2"}) == {"a": "1", "b": "2"}

    def test_nested_dict(self):
        result = flatten({"a": {"b": {"c": "deep"}}})
        assert result == {"a.b.c": "deep"}

    def test_mixed_depth(self):
        data = {"top": "value", "nested": {"key": "val"}}
        result = flatten(data)
        assert result == {"top": "value", "nested.key": "val"}

    def test_empty_dict(self):
        assert flatten({}) == {}

    def test_non_dict_root(self):
        # Non-dict root with no parent returns empty dict
        assert flatten("string") == {}

    def test_empty_nested_dict_preserved(self):
        result = flatten({"section": {}})
        assert result == {"section": {}}


class TestUnflatten:
    def test_roundtrip(self):
        original = {"a": {"b": "val", "c": "other"}, "top": "t"}
        flat = flatten(original)
        reconstructed = unflatten(flat)
        assert reconstructed == original

    def test_single_key(self):
        assert unflatten({"a.b.c": "deep"}) == {"a": {"b": {"c": "deep"}}}


# ---------------------------------------------------------------------------
# find_missing
# ---------------------------------------------------------------------------

class TestFindMissing:
    def _make_locale_dir(self, tmp_path: Path, locale: str, data: dict) -> None:
        locale_dir = tmp_path / locale
        locale_dir.mkdir(parents=True)
        for ns, content in data.items():
            (locale_dir / f"{ns}.json").write_text(
                json.dumps(content, ensure_ascii=False), encoding="utf-8"
            )

    def test_detects_missing_top_level_keys(self, tmp_path):
        self._make_locale_dir(tmp_path, "en", {"common": {"hello": "Hello", "world": "World"}})
        self._make_locale_dir(tmp_path, "de", {"common": {"hello": "Hallo"}})

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "common" in result
        assert "world" in result["common"]
        assert "hello" not in result["common"]  # already translated (different value)

    def test_detects_missing_nested_keys(self, tmp_path):
        """Critical: competitor PR #2 failed this test."""
        self._make_locale_dir(tmp_path, "en", {
            "common": {
                "top": "Top Level",
                "nested": {
                    "deep": "Deep Value",
                    "another": "Another Value",
                }
            }
        })
        self._make_locale_dir(tmp_path, "de", {
            "common": {
                "top": "Obere Ebene",
                "nested": {
                    "deep": "Tiefer Wert",
                    # "another" is missing
                }
            }
        })

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "common" in result
        assert "nested.another" in result["common"]
        assert "nested.deep" not in result["common"]
        assert "top" not in result["common"]

    def test_returns_empty_when_all_keys_present(self, tmp_path):
        self._make_locale_dir(tmp_path, "en", {"common": {"hello": "Hello"}})
        self._make_locale_dir(tmp_path, "de", {"common": {"hello": "Hallo"}})

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert result == {}

    def test_handles_empty_locale_file(self, tmp_path):
        self._make_locale_dir(tmp_path, "en", {"common": {"hello": "Hello", "world": "World"}})
        self._make_locale_dir(tmp_path, "de", {"common": {}})

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "common" in result
        assert "hello" in result["common"]
        assert "world" in result["common"]

    def test_missing_entire_namespace_file(self, tmp_path):
        self._make_locale_dir(tmp_path, "en", {"common": {"hello": "Hello"}})
        # de locale dir exists but has no common.json
        (tmp_path / "de").mkdir()

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "common" in result
        assert "hello" in result["common"]

    def test_source_dir_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Source locale dir not found"):
            find_missing(tmp_path / "nonexistent", tmp_path / "de")

    def test_untranslated_value_flagged_as_missing(self, tmp_path):
        """A value identical to source (and non-trivial) counts as missing."""
        self._make_locale_dir(tmp_path, "en", {"common": {"greeting": "Hello World"}})
        self._make_locale_dir(tmp_path, "de", {"common": {"greeting": "Hello World"}})

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "common" in result
        assert "greeting" in result["common"]

    def test_deeply_nested_keys_all_detected(self, tmp_path):
        """Three levels deep: a.b.c.d"""
        self._make_locale_dir(tmp_path, "en", {
            "app": {"ui": {"buttons": {"submit": "Submit", "cancel": "Cancel"}}}
        })
        self._make_locale_dir(tmp_path, "de", {
            "app": {"ui": {"buttons": {"submit": "Einreichen"}}}
        })

        result = find_missing(tmp_path / "en", tmp_path / "de")
        assert "ui.buttons.cancel" in result["app"]
        assert "ui.buttons.submit" not in result["app"]


# ---------------------------------------------------------------------------
# audit_all
# ---------------------------------------------------------------------------

class TestAuditAll:
    def _setup(self, tmp_path: Path):
        en = tmp_path / "en"
        de = tmp_path / "de"
        fr = tmp_path / "fr"
        en.mkdir(); de.mkdir(); fr.mkdir()
        (en / "common.json").write_text('{"a": "A", "b": {"c": "C"}}', encoding="utf-8")
        (de / "common.json").write_text('{"a": "AA"}', encoding="utf-8")
        (fr / "common.json").write_text('{"a": "A français", "b": {"c": "C français"}}', encoding="utf-8")
        return tmp_path

    def test_multiple_locales(self, tmp_path):
        self._setup(tmp_path)
        report = audit_all(tmp_path, "en", ["de", "fr"])
        # de is missing b.c
        assert "b.c" in report["de"]["common"]
        # fr has everything translated differently => no missing
        assert report["fr"] == {}

    def test_only_source_locale_present(self, tmp_path):
        en = tmp_path / "en"
        en.mkdir()
        (en / "common.json").write_text('{"hello": "Hello"}', encoding="utf-8")
        # ja doesn't exist
        (tmp_path / "ja").mkdir()
        report = audit_all(tmp_path, "en", ["ja"])
        assert "hello" in report["ja"]["common"]
