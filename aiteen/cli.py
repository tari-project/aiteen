"""Click-based CLI: aiteen audit | translate | patch | qa | run-all."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .audit import audit_all
from .config import Config
from .patch import patch_all
from .qa import run_qa
from .translate import translate_missing

console = Console()


def _handle_error(e: Exception) -> None:
    """Print a clean error message and exit 1."""
    click.echo(f"Error: {e}", err=True)
    sys.exit(1)


def _make_config(ctx_obj: dict) -> Config:
    if not ctx_obj.get("locales_dir") and not ctx_obj.get("config"):
        raise click.UsageError("Provide --locales-dir or --config")
    locales_dir = ctx_obj.get("locales_dir") or "."
    if not ctx_obj.get("config") and not Path(locales_dir).is_dir():
        raise FileNotFoundError(
            f"Locales directory not found: {locales_dir}"
        )
    return Config.load(
        locales_dir=locales_dir,
        config_file=ctx_obj.get("config"),
        source_locale=ctx_obj.get("source_locale"),
        target_locales=ctx_obj.get("target_locales"),
        openai_api_key=ctx_obj.get("openai_api_key"),
        openai_model=ctx_obj.get("openai_model"),
        dry_run=ctx_obj.get("dry_run", False),
    )


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="aiteen")
@click.option(
    "--locales-dir", "-d",
    type=click.Path(file_okay=False),
    help="Path to the locales directory (e.g., public/locales).",
)
@click.option("--config", "-c", type=click.Path(dir_okay=False),
              help="Path to a YAML config file.")
@click.option("--source-locale", default=None, help="Source locale code (default: en).")
@click.option("--target-locales", default=None,
              help="Comma-separated target locales. Auto-detected if omitted.")
@click.option("--openai-api-key", default=None, envvar="OPENAI_API_KEY")
@click.option("--openai-model", default=None, envvar="OPENAI_MODEL")
@click.option("--dry-run", is_flag=True, help="Don't write any files.")
@click.pass_context
def cli(ctx, locales_dir, config, source_locale, target_locales,
        openai_api_key, openai_model, dry_run):
    """Aiteen - robust AI-driven i18n translation pipeline."""
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None and not locales_dir and not config:
        click.echo(ctx.get_help())
    ctx.obj.update({
        "locales_dir": locales_dir,
        "config": config,
        "source_locale": source_locale,
        "target_locales": [t.strip() for t in target_locales.split(",")] if target_locales else None,
        "openai_api_key": openai_api_key,
        "openai_model": openai_model,
        "dry_run": dry_run,
    })


@cli.command("audit")
@click.option("--output", "-o", type=click.Path(dir_okay=False),
              help="Write JSON report to this path.")
@click.option("--fail-on-missing", is_flag=True,
              help="Exit with code 1 if any missing keys are found.")
@click.pass_context
def cmd_audit(ctx, output, fail_on_missing):
    """Detect missing translations across locale files."""
    try:
        cfg = _make_config(ctx.obj)
        report = audit_all(cfg.locales_dir, cfg.source_locale, cfg.target_locales)
        _print_audit_table(cfg, report)
        if output:
            Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
            console.print(f"[green]Wrote audit report to {output}[/green]")
        total = sum(len(items) for ns in report.values() for items in ns.values())
        if fail_on_missing and total > 0:
            sys.exit(1)
    except (ValueError, OSError, FileNotFoundError) as e:
        _handle_error(e)


@cli.command("translate")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, dir_okay=False),
              help="Audit report JSON to translate (skips re-running audit).")
@click.option("--output", "-o", type=click.Path(dir_okay=False),
              help="Write translations JSON to this path.")
@click.pass_context
def cmd_translate(ctx, input_path, output):
    """Translate missing strings via OpenAI."""
    try:
        cfg = _make_config(ctx.obj)
        if input_path:
            with open(input_path, "r", encoding="utf-8") as fh:
                audit = json.load(fh)
        else:
            audit = audit_all(cfg.locales_dir, cfg.source_locale, cfg.target_locales)
        translations = translate_missing(cfg, audit)
        if output:
            Path(output).write_text(json.dumps(translations, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        total = sum(len(items) for ns in translations.values() for items in ns.values())
        console.print(f"[green]Translated {total} strings[/green]")
    except (RuntimeError, ValueError, OSError, FileNotFoundError) as e:
        _handle_error(e)


@cli.command("patch")
@click.option("--input", "-i", "input_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Translations JSON file produced by `aiteen translate`.")
@click.pass_context
def cmd_patch(ctx, input_path):
    """Merge translated strings into locale files."""
    try:
        cfg = _make_config(ctx.obj)
        with open(input_path, "r", encoding="utf-8") as fh:
            translations = json.load(fh)
        counts = patch_all(cfg.locales_dir, translations, dry_run=cfg.dry_run)
        for locale, ns_counts in counts.items():
            for ns, n in ns_counts.items():
                console.print(f"  {locale}/{ns}.json  +{n} keys"
                              + (" (dry-run)" if cfg.dry_run else ""))
    except (ValueError, OSError, FileNotFoundError) as e:
        _handle_error(e)


@cli.command("qa")
@click.option("--fail-on-issue", is_flag=True, help="Exit 1 if any QA issue found.")
@click.pass_context
def cmd_qa(ctx, fail_on_issue):
    """Run QA checks on translated locale files."""
    try:
        cfg = _make_config(ctx.obj)
        report = run_qa(cfg.locales_dir, cfg.source_locale, cfg.target_locales)
        if report.ok:
            console.print(f"[green]QA passed - {report.files_checked} files, "
                          f"{report.keys_checked} keys checked.[/green]")
        else:
            table = Table(title="QA Issues")
            for col in ("Locale", "Namespace", "Key", "Code", "Detail"):
                table.add_column(col)
            for issue in report.issues:
                table.add_row(issue.locale, issue.namespace, issue.key,
                              issue.code, issue.detail)
            console.print(table)
            console.print(f"[red]{len(report.issues)} issue(s) across "
                          f"{report.files_checked} files.[/red]")
            if fail_on_issue:
                sys.exit(1)
    except (ValueError, OSError, FileNotFoundError) as e:
        _handle_error(e)


@cli.command("run-all")
@click.option("--skip-translate", is_flag=True,
              help="Audit + QA only; skip the OpenAI translation step.")
@click.pass_context
def cmd_run_all(ctx, skip_translate):
    """Audit - translate - patch - QA in one shot."""
    try:
        cfg = _make_config(ctx.obj)
    except (click.UsageError, FileNotFoundError, ValueError, OSError) as e:
        _handle_error(e)
        return
    try:
        console.rule("[bold]1/4 Audit")
        audit = audit_all(cfg.locales_dir, cfg.source_locale, cfg.target_locales)
        _print_audit_table(cfg, audit)
        total_missing = sum(len(items) for ns in audit.values() for items in ns.values())
        if total_missing == 0:
            console.print("[green]Nothing to translate. Done.[/green]")
            return
        if skip_translate:
            console.print("[yellow]--skip-translate set; stopping after audit.[/yellow]")
            return

        console.rule("[bold]2/4 Translate")
        translations = translate_missing(cfg, audit)

        console.rule("[bold]3/4 Patch")
        counts = patch_all(cfg.locales_dir, translations, dry_run=cfg.dry_run)
        for locale, ns_counts in counts.items():
            for ns, n in ns_counts.items():
                console.print(f"  {locale}/{ns}.json  +{n} keys"
                              + (" (dry-run)" if cfg.dry_run else ""))

        console.rule("[bold]4/4 QA")
        qa_report = run_qa(cfg.locales_dir, cfg.source_locale, cfg.target_locales)
        if qa_report.ok:
            console.print(f"[green]QA passed - {qa_report.files_checked} files, "
                          f"{qa_report.keys_checked} keys checked.[/green]")
        else:
            console.print(f"[red]QA found {len(qa_report.issues)} issue(s).[/red]")
            for issue in qa_report.issues[:20]:
                console.print(f"  {issue.locale}/{issue.namespace} {issue.key}: "
                              f"{issue.code} - {issue.detail}")
            sys.exit(1)
    except (RuntimeError, ValueError, OSError, FileNotFoundError) as e:
        _handle_error(e)


def _print_audit_table(cfg: Config, report: dict) -> None:
    table = Table(title=f"Missing translations vs '{cfg.source_locale}'")
    table.add_column("Locale")
    table.add_column("Namespace")
    table.add_column("Missing", justify="right")
    grand_total = 0
    for locale, namespaces in report.items():
        if not namespaces:
            table.add_row(locale, "-", "0")
            continue
        for ns, items in namespaces.items():
            table.add_row(locale, ns, str(len(items)))
            grand_total += len(items)
    console.print(table)
    console.print(f"[bold]Total missing: {grand_total}[/bold]")


if __name__ == "__main__":
    cli()
