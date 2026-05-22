"""Typer CLI."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, ValidationError

from x_impersonation_guard.clients.x_api import XApiClient
from x_impersonation_guard.config import AppConfig, load_config, write_default_config
from x_impersonation_guard.detection import run_scan
from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import (
    AccountProfile,
    QueueStatus,
    ScoreResult,
)
from x_impersonation_guard.reporters.rate_limit import check_report_limit
from x_impersonation_guard.reporters.x_help_form import XHelpFormReporter
from x_impersonation_guard.review.tui import ReviewQueueApp
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.storage.repository import ReviewStore, profile_from_record
from x_impersonation_guard.utils.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="X impersonation detection and reporting.")


class FixtureScan(BaseModel):
    protected: AccountProfile
    candidates: list[AccountProfile]


class FixtureLookup(XProfileLookup):
    def __init__(
        self, protected: AccountProfile, candidates: list[AccountProfile]
    ) -> None:
        self.protected = protected
        self.by_username = {profile.username.lower(): profile for profile in candidates}
        self.by_username[protected.username.lower()] = protected
        self.candidates = candidates

    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        return self.by_username.get(username.lower())

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        needle = display_name.lower()
        return [
            profile for profile in self.candidates if needle in profile.name.lower()
        ]

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        del user_id
        return self.candidates[:limit]


@app.command()
def init(
    config: Annotated[Path, typer.Option("--config", help="Config path.")] = Path(
        "config.yaml"
    ),
) -> None:
    """Create a default config for @wheelieinvestor."""
    write_default_config(config)
    typer.echo(f"Wrote {config}")
    _print_safety_warning()


@app.command()
def scan(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    fixture: Annotated[Path | None, typer.Option("--fixture")] = None,
) -> None:
    """Run detection and scoring."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity)
    store = ReviewStore(cfg.storage.db_path)
    if fixture:
        scan_fixture = FixtureScan.model_validate_json(fixture.read_text())
        lookup: XProfileLookup = FixtureLookup(
            scan_fixture.protected, scan_fixture.candidates
        )
    else:
        token = os.getenv(cfg.x_api.bearer_token_env)
        if not token:
            raise typer.BadParameter(
                f"{cfg.x_api.bearer_token_env} is not set. Use --fixture for offline scan."
            )
        lookup = XApiClient(token)
    results = asyncio.run(run_scan(cfg, selected, lookup, store))
    _render_scores(results)


@app.command("scan-fixture")
def scan_fixture_command(
    input: Annotated[Path, typer.Option("--input")],
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Score candidate accounts from a local JSON fixture."""
    scan(config=config, fixture=input)
    typer.echo("No reports were submitted. Review and report explicitly.")


@app.command("list")
def list_command(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
) -> None:
    """List pending review queue."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity)
    store = ReviewStore(cfg.storage.db_path)
    records = store.list_queue(selected.handle)
    if not records:
        typer.echo("No pending candidates.")
        return
    for record in records:
        typer.echo(
            f"{record.id}: @{record.handle} score={record.score} priority={record.priority} status={record.status}"
        )


@app.command()
def review(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    approve: Annotated[int | None, typer.Option("--approve")] = None,
    dismiss: Annotated[int | None, typer.Option("--dismiss")] = None,
    tui: Annotated[bool, typer.Option("--tui/--no-tui")] = False,
) -> None:
    """Approve, dismiss, or open the review queue."""
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    if approve is not None:
        store.set_status(approve, QueueStatus.APPROVED)
        typer.echo(f"Approved candidate {approve}")
        return
    if dismiss is not None:
        store.set_status(dismiss, QueueStatus.DISMISSED)
        typer.echo(f"Dismissed candidate {dismiss}")
        return
    if tui:
        ReviewQueueApp(store).run()
        return
    for record in store.list_queue():
        typer.echo(
            f"{record.id}: @{record.handle} score={record.score} priority={record.priority}"
        )


@app.command()
def report(
    candidate_id: int,
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    execute: Annotated[
        bool, typer.Option("--execute", help="Submit live form.")
    ] = False,
) -> None:
    """Create evidence package or submit an approved candidate."""
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    record = store.get_candidate(candidate_id)
    if record is None:
        raise typer.BadParameter(f"candidate not found: {candidate_id}")
    if record.status != QueueStatus.APPROVED.value and not execute:
        typer.echo("Dry run evidence package only. Approve before live submission.")
    if execute and record.status != QueueStatus.APPROVED.value:
        raise typer.BadParameter("live reports require approved review status")
    decision = check_report_limit(store, record.identity_handle, cfg.reporting)
    if execute and not decision.allowed:
        raise typer.BadParameter(decision.message)

    identity = cfg.identity_for_handle(record.identity_handle)
    candidate = profile_from_record(record)
    protected = AccountProfile(
        id=identity.user_id or identity.handle,
        username=identity.handle,
        name=identity.display_name,
    )
    score = score_candidate(protected, candidate, identity, cfg.scoring)
    reporter = XHelpFormReporter(
        reports_dir=cfg.storage.reports_dir,
        evidence_dir=cfg.storage.evidence_dir,
        user_data_dir=Path("~/.x-impersonation-guard/browser").expanduser(),
        headless=cfg.reporting.headless,
        dry_run=not execute,
    )
    if execute:
        _print_safety_warning()
    result = asyncio.run(reporter.submit(identity, candidate_id, candidate, score))
    status = "submitted" if result.submitted else "dry_run"
    store.record_report(
        candidate_id,
        record.identity_handle,
        candidate.username,
        status,
        result.report_dir,
    )
    if result.submitted:
        store.set_status(candidate_id, QueueStatus.REPORTED)
    typer.echo(f"{result.message}: {result.report_dir}")
    if execute:
        low, high = cfg.reporting.delay_between_reports_seconds
        typer.echo(f"Pacing enabled. Next submission should wait {low}-{high} seconds.")


@app.command()
def log(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
) -> None:
    """Show report history."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity) if identity else None
    store = ReviewStore(cfg.storage.db_path)
    for record in store.list_reports(selected.handle if selected else None):
        typer.echo(
            f"{record.created_at.isoformat()} candidate={record.candidate_id} @{record.candidate_handle} status={record.status} dir={record.report_dir}"
        )


@app.command()
def status(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Show queue and 24-hour report counts."""
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    for identity in cfg.protected_identities:
        pending = len(store.list_queue(identity.handle))
        reports = store.reports_in_window(identity.handle)
        typer.echo(
            f"@{identity.handle}: pending={pending} reports_24h={reports}/{cfg.reporting.max_reports_per_24h}"
        )


@app.command()
def daemon(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    every_hours: Annotated[float, typer.Option("--every-hours")] = 6.0,
) -> None:
    """Run scans in a simple foreground loop."""
    while True:
        scan(config=config)
        time.sleep(every_hours * 3600)


@app.command()
def export(
    format: Annotated[str, typer.Argument(help="zip or json")],
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Export queued candidates."""
    if format != "json":
        raise typer.BadParameter("only json export is implemented in alpha")
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    records = store.list_queue()
    payload = [
        {
            "id": record.id,
            "identity": record.identity_handle,
            "handle": record.handle,
            "score": record.score,
            "priority": record.priority,
            "status": record.status,
            "score_breakdown": json.loads(record.score_breakdown_json or "{}"),
        }
        for record in records
    ]
    typer.echo(json.dumps(payload, indent=2, default=str))


def _load(path: Path) -> AppConfig:
    try:
        cfg = load_config(path)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Config invalid: {exc}", err=True)
        raise typer.Exit(1) from exc
    configure_logging(cfg.logging.level, cfg.logging.format == "json")
    if cfg.reporting.auto_submit:
        _print_safety_warning()
    return cfg


def _render_scores(results: list[ScoreResult]) -> None:
    if not results:
        typer.echo("No candidates found.")
        return
    for result in results:
        typer.echo(
            f"@{result.candidate.username}: score={result.score} priority={result.priority} queue={result.queue}"
        )
        if result.reasons:
            typer.echo(f"  reasons: {', '.join(result.reasons)}")
        if result.mitigations:
            typer.echo(f"  mitigations: {', '.join(result.mitigations)}")


def _print_safety_warning() -> None:
    typer.secho(
        "WARNING: automated reporting can put the reporter account at risk. Manual review is strongly recommended.",
        fg=typer.colors.YELLOW,
        err=True,
    )


if __name__ == "__main__":
    app()
