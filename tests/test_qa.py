"""Tests for aiteen.qa — placeholder validation and QA reporting."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiteen.qa import QAReport, qa_locale, run_qa


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# qa_locale
# ---------------------------------------------------------------------------

class TestQaLocale:
    def test_catches_placeholder_stripping(self, tmp_path):
        """If {count} is removed in the translation, QA must flag it."""
        _write_json(tmp_path / "en" / "common.json", {"items": "{count} items"})
        _write_json(tmp_path / "de" / "common.json", {"items": "Artikel"})  # {count} stripped!

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "PLACEHOLDER_MISMATCH" in codes

    def test_catches_html_placeholder_stripping(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"label": "<b>Bold</b> text"})
        _write_json(tmp_path / "de" / "common.json", {"label": "Fetter Text"})  # tags stripped!

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "PLACEHOLDER_MISMATCH" in codes

    def test_accepts_valid_translations(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello", "world": "World"})
        _write_json(tmp_path / "de" / "common.json", {"hello": "Hallo", "world": "Welt"})

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        assert report.ok
        assert report.keys_checked == 2

    def test_handles_empty_string_values(self, tmp_path):
        """Empty strings should not cause errors."""
        _write_json(tmp_path / "en" / "common.json", {"empty": "", "normal": "Hi"})
        _write_json(tmp_path / "de" / "common.json", {"empty": "", "normal": "Hallo"})

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        # Empty string key should not trigger PLACEHOLDER_MISMATCH
        for issue in report.issues:
            if issue.key == "empty":
                assert issue.code != "PLACEHOLDER_MISMATCH"

    def test_missing_key_flagged(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello", "world": "World"})
        _write_json(tmp_path / "de" / "common.json", {"hello": "Hallo"})

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "MISSING_KEY" in codes

    def test_missing_namespace_flagged(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello"})
        # de dir exists but no common.json
        (tmp_path / "de").mkdir()

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "MISSING_NAMESPACE" in codes

    def test_missing_locale_dir_flagged(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello"})
        # de dir does not exist at all

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "MISSING_LOCALE_DIR" in codes

    def test_untranslated_value_flagged(self, tmp_path):
        """Target value identical to source (non-trivial) is flagged UNTRANSLATED."""
        _write_json(tmp_path / "en" / "common.json", {"title": "Dashboard Overview"})
        _write_json(tmp_path / "de" / "common.json", {"title": "Dashboard Overview"})

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "UNTRANSLATED" in codes

    def test_placeholder_preserved_no_issue(self, tmp_path):
        """When placeholders are preserved, no PLACEHOLDER_MISMATCH."""
        _write_json(tmp_path / "en" / "common.json", {"items": "{count} items"})
        _write_json(tmp_path / "de" / "common.json", {"items": "{count} Artikel"})

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        placeholder_issues = [i for i in report.issues if i.code == "PLACEHOLDER_MISMATCH"]
        assert len(placeholder_issues) == 0

    def test_deeply_nested_placeholder_checked(self, tmp_path):
        """QA must check nested keys for placeholder integrity."""
        _write_json(tmp_path / "en" / "app.json", {
            "ui": {"status": "Synced {count} of {total} items"}
        })
        _write_json(tmp_path / "de" / "app.json", {
            "ui": {"status": "Synchronisiert Artikel"}  # both placeholders stripped
        })

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        mismatch = [i for i in report.issues if i.code == "PLACEHOLDER_MISMATCH"]
        assert len(mismatch) > 0
        assert mismatch[0].key == "ui.status"

    def test_malformed_json_flagged(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello"})
        (tmp_path / "de").mkdir(parents=True)
        (tmp_path / "de" / "common.json").write_text("{bad json", encoding="utf-8")

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        codes = [i.code for i in report.issues]
        assert "INVALID_JSON" in codes

    def test_increments_counters(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {
            "a": "Alpha", "b": "Beta", "c": "Gamma"
        })
        _write_json(tmp_path / "de" / "common.json", {
            "a": "Alfa", "b": "Beta-de", "c": "Gamma-de"
        })

        report = QAReport()
        qa_locale(tmp_path, "en", "de", report)

        assert report.files_checked == 1
        assert report.keys_checked == 3


# ---------------------------------------------------------------------------
# run_qa
# ---------------------------------------------------------------------------

class TestRunQa:
    def test_run_qa_clean(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello"})
        _write_json(tmp_path / "de" / "common.json", {"hello": "Hallo"})
        _write_json(tmp_path / "fr" / "common.json", {"hello": "Bonjour"})

        report = run_qa(tmp_path, "en", ["de", "fr"])
        assert report.ok

    def test_run_qa_with_issues(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"items": "{count} items"})
        _write_json(tmp_path / "de" / "common.json", {"items": "Artikel"})

        report = run_qa(tmp_path, "en", ["de"])
        assert not report.ok
        assert any(i.code == "PLACEHOLDER_MISMATCH" for i in report.issues)

    def test_empty_target_locales(self, tmp_path):
        _write_json(tmp_path / "en" / "common.json", {"hello": "Hello"})
        report = run_qa(tmp_path, "en", [])
        assert report.ok
        assert report.files_checked == 0
