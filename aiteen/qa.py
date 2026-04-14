"""Quality-assurance checks on translated locale files.

Validates:
  - Every locale file is valid JSON.
  - All keys present in the source locale exist in each target locale.
  - Placeholders ({var}, {{var}}, %s, %d, <tag>) are preserved verbatim.
  - Translated string length is within sanity bounds (configurable factor).
  - Translated values differ from source for non-trivial strings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audit import flatten, list_namespaces, load_json
from .translate import extract_placeholders


@dataclass
class QAIssue:
    locale: str
    namespace: str
    key: str
    code: str
    detail: str


@dataclass
class QAReport:
    issues: list[QAIssue] = field(default_factory=list)
    files_checked: int = 0
    keys_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues

    def add(self, locale, namespace, key, code, detail):
        self.issues.append(QAIssue(locale, namespace, key, code, detail))


def _length_ok(src: str, tgt: str, max_factor: float = 4.0) -> bool:
    if not src:
        return True
    return len(tgt) <= max(20, int(len(src) * max_factor))


def qa_locale(
    locales_dir: Path,
    source_locale: str,
    target_locale: str,
    report: QAReport,
) -> None:
    src_dir = locales_dir / source_locale
    tgt_dir = locales_dir / target_locale
    if not tgt_dir.is_dir():
        report.add(target_locale, "*", "*", "MISSING_LOCALE_DIR",
                   f"Locale directory does not exist: {tgt_dir}")
        return

    for ns in list_namespaces(src_dir):
        src_path = src_dir / f"{ns}.json"
        tgt_path = tgt_dir / f"{ns}.json"
        if not tgt_path.is_file():
            report.add(target_locale, ns, "*", "MISSING_NAMESPACE",
                       f"File not found: {tgt_path}")
            continue
        try:
            src = flatten(load_json(src_path))
            tgt = flatten(load_json(tgt_path))
        except (ValueError, OSError) as e:
            report.add(target_locale, ns, "*", "INVALID_JSON", str(e))
            continue
        report.files_checked += 1

        for key, src_val in src.items():
            if not isinstance(src_val, str):
                continue
            report.keys_checked += 1
            if key not in tgt:
                report.add(target_locale, ns, key, "MISSING_KEY",
                           "Key absent in target locale")
                continue
            tgt_val = tgt[key]
            if not isinstance(tgt_val, str):
                report.add(target_locale, ns, key, "TYPE_MISMATCH",
                           f"Expected string, got {type(tgt_val).__name__}")
                continue

            src_ph = extract_placeholders(src_val)
            tgt_ph = extract_placeholders(tgt_val)
            if sorted(src_ph) != sorted(tgt_ph):
                report.add(
                    target_locale, ns, key, "PLACEHOLDER_MISMATCH",
                    f"source={src_ph} target={tgt_ph}",
                )
            if not _length_ok(src_val, tgt_val):
                report.add(target_locale, ns, key, "LENGTH_OUT_OF_BOUNDS",
                           f"src_len={len(src_val)} tgt_len={len(tgt_val)}")
            if src_val.strip() and tgt_val == src_val and len(src_val) > 3:
                report.add(target_locale, ns, key, "UNTRANSLATED",
                           "Target value identical to source")


def run_qa(
    locales_dir: Path,
    source_locale: str,
    target_locales: list[str],
) -> QAReport:
    report = QAReport()
    for loc in target_locales:
        qa_locale(locales_dir, source_locale, loc, report)
    return report
