"""Typer CLI."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import shlex
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from x_impersonation_guard import __version__
from x_impersonation_guard.clients.cost_guard import (
    ApiCostBudgetExceeded,
    CostGuardedLookup,
)
from x_impersonation_guard.clients.mode_selector import select_scan_mode
from x_impersonation_guard.clients.x_api import XApiClient
from x_impersonation_guard.clients.x_scrape import XScrapeClient
from x_impersonation_guard.config import (
    AppConfig,
    default_config_dict,
    load_config,
    write_default_config,
)
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
from x_impersonation_guard.storage.models import CandidateRecord
from x_impersonation_guard.storage.repository import ReviewStore, profile_from_record
from x_impersonation_guard.utils.logging import configure_logging

app = typer.Typer(help="X impersonation detection and reporting.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"x-impersonation-guard {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the installed x-impersonation-guard version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """X impersonation detection and reporting."""
    del version
    if ctx.invoked_subcommand is not None:
        return
    if not Path("config.yaml").exists():
        typer.echo(
            "It looks like this is your first run. Try `xig scan-fixture` for an offline demo, or `xig init` to set up against your real account."
        )
        raise typer.Exit()
    typer.echo(ctx.get_help())
    raise typer.Exit()


class FixtureScan(BaseModel):
    protected: AccountProfile
    candidates: list[AccountProfile]


class CalibrationCandidate(BaseModel):
    profile: AccountProfile
    expected_impersonator: bool
    note: str | None = None


class CalibrationSet(BaseModel):
    protected: AccountProfile
    candidates: list[CalibrationCandidate]


class DemoProtectedIdentity(BaseModel):
    handle: str
    display_name: str
    user_id: str
    bio: str = ""
    follower_count: int = 100_000
    account_age_days: int = 2_000
    verified: bool = False
    profile_image_hash: str
    protected_pic: list[str] = []


class DemoCandidate(BaseModel):
    handle: str
    display_name: str
    bio: str
    follower_count: int
    account_age_days: int
    profile_image_hash: str
    verified: bool = False
    protected_followers_followed: int = 0
    mutual_followers: int = 0
    tweet_count: int | None = None
    posts_containing_protected_handle: int | None = None
    first_detected_hours_ago: float = 0.0
    sample_posts: list[str] = []
    candidate_pic: list[str] = []
    expected_score_range: tuple[int, int]
    expected_tier: str


class DemoFixture(BaseModel):
    demo_protected_identity: DemoProtectedIdentity
    demo_candidates: list[DemoCandidate]

    def to_fixture_scan(self) -> FixtureScan:
        now = datetime.now(UTC)
        protected = AccountProfile(
            id=self.demo_protected_identity.user_id,
            username=self.demo_protected_identity.handle,
            name=self.demo_protected_identity.display_name,
            description=self.demo_protected_identity.bio,
            followers_count=self.demo_protected_identity.follower_count,
            verified=self.demo_protected_identity.verified,
            created_at=now
            - timedelta(days=self.demo_protected_identity.account_age_days),
            profile_image_phash=self.demo_protected_identity.profile_image_hash,
        )
        candidates = [
            AccountProfile(
                id=str(index + 2_000_000_000),
                username=candidate.handle,
                name=candidate.display_name,
                description=candidate.bio,
                verified=candidate.verified,
                followers_count=candidate.follower_count,
                following_count=750 if candidate.follower_count < 50 else 200,
                tweet_count=candidate.tweet_count
                if candidate.tweet_count is not None
                else 3
                if candidate.account_age_days < 30
                else 150,
                protected_followers_followed=candidate.protected_followers_followed,
                mutual_followers=candidate.mutual_followers,
                recent_posts_containing_protected_handle=candidate.posts_containing_protected_handle
                if candidate.posts_containing_protected_handle is not None
                else sum(
                    1
                    for post in candidate.sample_posts
                    if self.demo_protected_identity.handle.lower() in post.lower()
                ),
                created_at=now - timedelta(days=candidate.account_age_days),
                profile_image_phash=candidate.profile_image_hash,
            )
            for index, candidate in enumerate(self.demo_candidates)
        ]
        return FixtureScan(protected=protected, candidates=candidates)


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
    guided: Annotated[
        bool,
        typer.Option(
            "--guided/--no-guided",
            help="Prompt for the identity fields instead of writing placeholders.",
        ),
    ] = False,
    handle: Annotated[
        str | None,
        typer.Option(
            "--handle",
            help="Protected X handle, with or without @.",
        ),
    ] = None,
    display_name: Annotated[
        str | None,
        typer.Option(
            "--display-name",
            help="Public display name to protect.",
        ),
    ] = None,
    reporter_name: Annotated[
        str | None,
        typer.Option(
            "--reporter-name",
            help="Name to use in Help Center report contact fields.",
        ),
    ] = None,
    reporter_email: Annotated[
        str | None,
        typer.Option(
            "--reporter-email",
            help="Email to use in Help Center report contact fields.",
        ),
    ] = None,
) -> None:
    """Create a starter config for your protected account."""
    if guided:
        handle, display_name, reporter_name, reporter_email = _prompt_init_fields(
            handle=handle,
            display_name=display_name,
            reporter_name=reporter_name,
            reporter_email=reporter_email,
        )
    write_default_config(
        config,
        handle=handle,
        display_name=display_name,
        reporter_name=reporter_name,
        reporter_email=reporter_email,
    )
    typer.echo(f"Wrote {config}")
    if handle is None or display_name is None or reporter_email is None:
        typer.echo(
            "Edit the starter identity fields before running a live scan, or rerun with `--guided`, `--handle`, `--display-name`, and `--reporter-email`."
        )
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
        decision = select_scan_mode(cfg)
        typer.echo(f"Scan mode: {decision.mode.value} ({decision.reason})")
        if decision.bearer_token:
            lookup = CostGuardedLookup(
                XApiClient(decision.bearer_token),
                max_cost_usd=cfg.x_api.max_cost_per_scan_usd,
                estimated_cost_per_request_usd=cfg.x_api.estimated_cost_per_request_usd,
            )
            typer.echo(
                "API scan budget: "
                f"max_estimated=${cfg.x_api.max_cost_per_scan_usd:.2f} "
                f"estimated_per_request=${cfg.x_api.estimated_cost_per_request_usd:.2f} "
                f"max_requests={lookup.max_calls}"
            )
        else:
            lookup = XScrapeClient(
                str(Path("~/.x-impersonation-guard/browser").expanduser()),
                headless=cfg.reporting.headless,
            )
    try:
        results = asyncio.run(run_scan(cfg, selected, lookup, store))
    except ApiCostBudgetExceeded as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render_scores(results)


@app.command("scan-fixture")
def scan_fixture_command(
    input: Annotated[Path, typer.Option("--input")] = Path(
        "examples/demo_fixture.json"
    ),
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Run the bundled offline demo fixture with no network calls."""
    if config.expanduser().exists():
        cfg = _load(config)
        wrote_config = False
    else:
        cfg = _demo_config()
        config.expanduser().parent.mkdir(parents=True, exist_ok=True)
        config.expanduser().write_text(
            yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False)
        )
        typer.echo(f"Wrote demo config to {config}")
        wrote_config = True
    fixture_path = _resolve_fixture_path(input)
    raw = json.loads(fixture_path.read_text())
    if "demo_protected_identity" in raw:
        demo_fixture = DemoFixture.model_validate(raw)
        scan_fixture = demo_fixture.to_fixture_scan()
        cfg = _config_for_demo_fixture(cfg, scan_fixture)
        if wrote_config:
            config.expanduser().write_text(
                yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False)
            )
    else:
        demo_fixture = None
        scan_fixture = FixtureScan.model_validate(raw)
    store = ReviewStore(cfg.storage.db_path)
    lookup = FixtureLookup(scan_fixture.protected, scan_fixture.candidates)
    results = asyncio.run(run_scan(cfg, cfg.protected_identities[0], lookup, store))
    if demo_fixture is not None:
        _apply_demo_detection_times(
            store, cfg.protected_identities[0].handle, demo_fixture
        )
    high = sum(
        1
        for result in results
        if result.priority is not None and result.priority.value in {"high", "critical"}
    )
    medium = sum(
        1
        for result in results
        if result.priority is not None and result.priority.value == "medium"
    )
    queued = high + medium
    typer.echo(
        f"Demo scan complete. {queued} candidates queued ({high} high, {medium} medium). "
        "Run `xig review` to see them, or `xig list` for a summary."
    )
    typer.echo("No reports were submitted. Review and report explicitly.")


@app.command()
def calibrate(
    input: Annotated[Path, typer.Option("--input")] = Path(
        "examples/calibration.sample.json"
    ),
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    threshold: Annotated[
        int | None,
        typer.Option(
            "--threshold",
            help="Score threshold treated as predicted impersonation.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Optional JSON file for calibration evidence.",
        ),
    ] = None,
) -> None:
    """Evaluate scorer precision and recall against a labeled offline set."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity)
    calibration = CalibrationSet.model_validate_json(input.expanduser().read_text())
    cutoff = (
        threshold
        if threshold is not None
        else cfg.scoring.thresholds.review_queue_medium
    )
    if cutoff < 0 or cutoff > 100:
        raise typer.BadParameter("threshold must be between 0 and 100")

    rows = []
    true_positive = false_positive = true_negative = false_negative = 0
    for item in calibration.candidates:
        result = score_candidate(
            calibration.protected,
            item.profile,
            selected,
            cfg.scoring,
        )
        predicted = result.score >= cutoff
        if predicted and item.expected_impersonator:
            true_positive += 1
        elif predicted and not item.expected_impersonator:
            false_positive += 1
        elif not predicted and item.expected_impersonator:
            false_negative += 1
        else:
            true_negative += 1
        rows.append((item, result, predicted))

    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    f1 = _ratio(2 * precision * recall, precision + recall)
    typer.echo(f"Calibration candidates: {len(calibration.candidates)}")
    typer.echo(
        f"threshold={cutoff} precision={precision:.2f} recall={recall:.2f} f1={f1:.2f} "
        f"tp={true_positive} fp={false_positive} tn={true_negative} fn={false_negative}"
    )
    misses = [
        (item, result, predicted)
        for item, result, predicted in rows
        if predicted != item.expected_impersonator
    ]
    if output is not None:
        _write_calibration_output(
            output=output,
            input_path=input,
            config_path=config,
            identity_handle=selected.handle,
            cutoff=cutoff,
            precision=precision,
            recall=recall,
            f1=f1,
            true_positive=true_positive,
            false_positive=false_positive,
            true_negative=true_negative,
            false_negative=false_negative,
            rows=rows,
            misses=misses,
        )
        typer.echo(f"Calibration evidence written to {output.expanduser()}")
    if not misses:
        typer.echo("No calibration misses.")
        return
    typer.echo("Calibration misses:")
    for item, result, predicted in misses:
        expected = "impersonator" if item.expected_impersonator else "benign"
        actual = "impersonator" if predicted else "benign"
        note = f" note={item.note}" if item.note else ""
        typer.echo(
            f"- @{item.profile.username} score={result.score} expected={expected} predicted={actual}{note}"
        )


def _write_calibration_output(
    *,
    output: Path,
    input_path: Path,
    config_path: Path,
    identity_handle: str,
    cutoff: int,
    precision: float,
    recall: float,
    f1: float,
    true_positive: int,
    false_positive: int,
    true_negative: int,
    false_negative: int,
    rows: list[tuple[CalibrationCandidate, ScoreResult, bool]],
    misses: list[tuple[CalibrationCandidate, ScoreResult, bool]],
) -> None:
    output_path = output.expanduser()
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input": str(input_path.expanduser()),
        "config": str(config_path.expanduser()),
        "identity_handle": identity_handle,
        "threshold": cutoff,
        "candidate_count": len(rows),
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
        },
        "misses": [
            _calibration_row_payload(item, result, predicted)
            for item, result, predicted in misses
        ],
        "candidates": [
            _calibration_row_payload(item, result, predicted)
            for item, result, predicted in rows
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _calibration_row_payload(
    item: CalibrationCandidate, result: ScoreResult, predicted: bool
) -> dict[str, Any]:
    return {
        "handle": item.profile.username,
        "profile_url": item.profile.handle_url,
        "score": result.score,
        "priority": result.priority.value if result.priority else None,
        "expected_impersonator": item.expected_impersonator,
        "predicted_impersonator": predicted,
        "correct": predicted == item.expected_impersonator,
        "note": item.note,
        "reasons": result.reasons,
        "mitigations": result.mitigations,
        "signals": result.signals.model_dump(mode="json"),
        "weighted_scores": result.weighted_scores,
    }


@app.command("list")
def list_command(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    status: Annotated[
        str,
        typer.Option(
            "--status",
            help="Queue status to list: pending, snoozed, approved, dismissed, reported, report_failed, failed, or all.",
        ),
    ] = QueueStatus.PENDING.value,
) -> None:
    """List review queue candidates."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity)
    store = ReviewStore(cfg.storage.db_path)
    selected_status = _parse_list_status(status)
    if selected_status is None:
        records = [
            record
            for queue_status in QueueStatus
            for record in store.list_queue(selected.handle, status=queue_status)
        ]
        records.sort(key=lambda record: (record.score, record.updated_at), reverse=True)
    else:
        records = store.list_queue(selected.handle, status=selected_status)
    if not records:
        typer.echo(f"No {_status_label(selected_status)} candidates.")
        return
    for record in records:
        typer.echo(
            f"{record.id}: @{record.handle} score={record.score} priority={record.priority} detected={_relative_age(record.created_at)} status={record.status}"
        )


@app.command()
def review(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    show: Annotated[
        int | None,
        typer.Option("--show", help="Show detailed evidence for a candidate ID."),
    ] = None,
    next_candidate: Annotated[
        bool,
        typer.Option(
            "--next",
            help="Show detailed evidence for the highest-priority pending candidate.",
        ),
    ] = False,
    approve: Annotated[int | None, typer.Option("--approve")] = None,
    dismiss: Annotated[int | None, typer.Option("--dismiss")] = None,
    snooze: Annotated[int | None, typer.Option("--snooze")] = None,
    restore: Annotated[
        int | None,
        typer.Option("--restore", help="Move a snoozed candidate back to pending."),
    ] = None,
    tui: Annotated[bool, typer.Option("--tui/--no-tui")] = False,
) -> None:
    """Approve, dismiss, or open the review queue."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity) if identity else None
    store = ReviewStore(cfg.storage.db_path)
    if next_candidate:
        record = _next_pending_candidate(store, selected.handle if selected else None)
        if record is None:
            typer.echo("No pending candidates.")
            return
        _render_review_detail(
            record,
            config_path=config,
            identity_handle=_command_identity_handle(cfg, selected, record),
        )
        return
    if show is not None:
        record = _get_review_candidate(
            store, show, selected.handle if selected else None
        )
        _render_review_detail(
            record,
            config_path=config,
            identity_handle=_command_identity_handle(cfg, selected, record),
        )
        return
    if approve is not None:
        record = _get_review_candidate(
            store, approve, selected.handle if selected else None
        )
        store.set_status(approve, QueueStatus.APPROVED)
        command_identity = _command_identity_handle(cfg, selected, record)
        typer.echo(f"Approved candidate {approve}")
        typer.echo(
            "Dry-run report: "
            f"{_report_command(approve, config, command_identity, '--dry-run')}"
        )
        typer.echo(
            "Live report after inspecting dry-run evidence: "
            f"{_report_command(approve, config, command_identity, '--execute --confirm-live')}"
        )
        return
    if dismiss is not None:
        _get_review_candidate(store, dismiss, selected.handle if selected else None)
        store.set_status(dismiss, QueueStatus.DISMISSED)
        typer.echo(f"Dismissed candidate {dismiss}")
        return
    if snooze is not None:
        _get_review_candidate(store, snooze, selected.handle if selected else None)
        store.set_status(snooze, QueueStatus.SNOOZED)
        typer.echo(f"Snoozed candidate {snooze}")
        return
    if restore is not None:
        _get_review_candidate(store, restore, selected.handle if selected else None)
        store.set_status(restore, QueueStatus.PENDING)
        typer.echo(f"Restored candidate {restore} to pending")
        return
    if tui:
        ReviewQueueApp(store).run()
        return
    records = store.list_queue(selected.handle if selected else None)
    _render_review_queue(records)


@app.command()
def report(
    candidate_id: int,
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Create evidence only or submit the live Help Center form.",
        ),
    ] = True,
    confirm_live: Annotated[
        bool,
        typer.Option(
            "--confirm-live",
            help="Required with --execute to acknowledge a live Help Center submission.",
        ),
    ] = False,
) -> None:
    """Create evidence package or submit an approved candidate."""
    cfg = _load(config)
    selected_identity = cfg.identity_for_handle(identity) if identity else None
    store = ReviewStore(cfg.storage.db_path)
    record = _get_review_candidate(
        store, candidate_id, selected_identity.handle if selected_identity else None
    )
    execute = not dry_run
    if record.status != QueueStatus.APPROVED.value and dry_run:
        typer.echo("Dry run evidence package only. Approve before live submission.")
    if execute and record.status != QueueStatus.APPROVED.value:
        raise typer.BadParameter("live reports require approved review status")
    if execute and not confirm_live:
        raise typer.BadParameter(
            "live Help Center submissions require --confirm-live in addition to --execute"
        )
    decision = check_report_limit(store, record.identity_handle, cfg.reporting)
    if execute and not decision.allowed:
        raise typer.BadParameter(decision.message)

    protected_identity = cfg.identity_for_handle(record.identity_handle)
    candidate = profile_from_record(record)
    protected = AccountProfile(
        id=protected_identity.user_id or protected_identity.handle,
        username=protected_identity.handle,
        name=protected_identity.display_name,
    )
    score = score_candidate(protected, candidate, protected_identity, cfg.scoring)
    reporter = XHelpFormReporter(
        reports_dir=cfg.storage.reports_dir,
        evidence_dir=cfg.storage.evidence_dir,
        user_data_dir=Path("~/.x-impersonation-guard/browser").expanduser(),
        headless=cfg.reporting.headless,
        dry_run=not execute,
    )
    if execute:
        _print_safety_warning()
    try:
        result = asyncio.run(
            reporter.submit(protected_identity, candidate_id, candidate, score)
        )
    except Exception as exc:
        store.record_report(
            candidate_id,
            record.identity_handle,
            candidate.username,
            QueueStatus.REPORT_FAILED.value,
            error=str(exc),
        )
        store.set_status(candidate_id, QueueStatus.REPORT_FAILED)
        raise typer.BadParameter(f"report failed: {exc}") from exc
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
    if not execute:
        typer.echo(
            f"For public bug reports, share `xig redact-report {result.report_dir}` output instead of the original package."
        )
        command_identity = _command_identity_handle(cfg, selected_identity, record)
        if record.status == QueueStatus.APPROVED.value:
            typer.echo(
                "Live report after inspecting evidence: "
                f"{_report_command(candidate_id, config, command_identity, '--execute --confirm-live')}"
            )
        else:
            typer.echo(
                "Approve before live submission: "
                f"{_review_command('approve', candidate_id, config, command_identity)}"
            )
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


@app.command("redact-report")
def redact_report(
    report_dir: Annotated[
        Path,
        typer.Argument(help="Report package directory created by `xig report`."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination .zip path."),
    ] = None,
) -> None:
    """Create a privacy-safe report bundle for public bug reports."""
    source = report_dir.expanduser()
    if not source.is_dir():
        raise typer.BadParameter(f"report directory not found: {source}")
    bundle_path = (
        output.expanduser()
        if output
        else source.with_name(f"{source.name}_redacted.zip")
    )
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    included = []
    redacted = []
    excluded = []
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.iterdir()):
            if not path.is_file():
                continue
            if path.suffix == ".json":
                payload = json.loads(path.read_text())
                archive.writestr(path.name, json.dumps(_redact_json(payload), indent=2))
                included.append(path.name)
                redacted.append(path.name)
            elif path.suffix in {".txt", ".log"}:
                archive.writestr(path.name, _redact_text(path.read_text()))
                included.append(path.name)
                redacted.append(path.name)
            else:
                excluded.append(path.name)
        manifest = {
            "source": source.name,
            "included": included,
            "redacted": redacted,
            "excluded": excluded,
            "note": "Screenshots and HTML are excluded because they can contain logged-in account data, cookies, email links, or private page content.",
        }
        archive.writestr("REDACTION_MANIFEST.json", json.dumps(manifest, indent=2))
    typer.echo(f"Created redacted report bundle: {bundle_path}")
    if excluded:
        typer.echo(
            "Excluded screenshots/HTML by default. Review them manually before sharing any originals."
        )


@app.command()
def status(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable queue and report status."),
    ] = False,
) -> None:
    """Show queue status and 24-hour report counts."""
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    identity_statuses: list[tuple[str, dict[str, int], int, int]] = []
    for identity in cfg.protected_identities:
        counts = store.queue_status_counts(identity.handle)
        reports = store.reports_in_window(identity.handle)
        identity_statuses.append(
            (identity.handle, counts, reports, cfg.reporting.max_reports_per_24h)
        )
    if json_output:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "identities": [
                {
                    "handle": handle,
                    "queue": counts,
                    "reports_24h": reports,
                    "reports_limit_24h": reports_limit,
                }
                for handle, counts, reports, reports_limit in identity_statuses
            ],
            "max_reports_per_24h": cfg.reporting.max_reports_per_24h,
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    for handle, counts, reports, reports_limit in identity_statuses:
        typer.echo(
            f"@{handle}: {_format_queue_counts(counts)} reports_24h={reports}/{reports_limit}"
        )


@app.command("validation-template")
def validation_template(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination Markdown file path."),
    ] = Path("live-validation-result.md"),
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    identity: Annotated[str | None, typer.Option("--identity")] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the destination if it already exists."),
    ] = False,
) -> None:
    """Write a controlled live-validation evidence checklist."""
    destination = output.expanduser()
    if destination.exists() and not force:
        typer.echo(
            f"{destination} already exists; pass --force to replace it",
            err=True,
        )
        raise typer.Exit(1)
    if destination.parent != Path("."):
        destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _render_validation_template(config.expanduser(), identity) + "\n"
    )
    typer.echo(f"Validation template written to {destination}")
    typer.echo("Do not paste API tokens, cookies, browser profiles, or private DMs.")


@app.command()
def quickstart(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Print the safest next commands for demo or real-account setup."""
    config_path = config.expanduser()
    typer.echo("x-impersonation-guard quickstart")
    typer.echo("")
    typer.echo("Safe offline demo:")
    _echo_commands(
        [
            "xig scan-fixture",
            "xig doctor",
            "xig review",
            "xig review --next",
            "xig report --dry-run 1",
        ]
    )
    typer.echo("")

    if not config_path.exists():
        typer.echo(f"No config found at {config_path}.")
        typer.echo("Real-account setup:")
        _echo_commands(
            [
                'export X_API_BEARER_TOKEN="..."',
                "xig init --guided",
                "xig doctor",
                "xig scan",
            ]
        )
        typer.echo("")
        typer.echo(
            "Nothing here submits a live report. Live reporting requires review approval plus `--execute --confirm-live`."
        )
        return

    try:
        cfg = load_config(config_path)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Config invalid at {config_path}: {exc}")
        typer.echo("Fix the config, then run `xig doctor`.")
        return

    identity_count = len(cfg.protected_identities)
    identity_label = "identity" if identity_count == 1 else "identities"
    typer.echo(
        f"Config found at {config_path}: {identity_count} protected {identity_label}."
    )
    for warning in _starter_identity_warnings(cfg):
        typer.echo(f"WARN: {warning}")
    token_name = cfg.x_api.bearer_token_env
    token_state = "set" if os.getenv(token_name) else "not set"
    typer.echo(f"{token_name}: {token_state}")
    typer.echo("")
    typer.echo("Recommended next commands:")
    _echo_commands(
        [
            f"xig doctor --config {config_path}",
            f"xig scan --config {config_path}",
            f"xig status --config {config_path}",
            f"xig status --config {config_path} --json",
            f"xig review --config {config_path}",
            f"xig review --config {config_path} --next",
            f"xig review --config {config_path} --show <candidate_id>",
            f"xig report --config {config_path} --dry-run <candidate_id>",
            f"xig validation-template --config {config_path}",
        ]
    )
    typer.echo("")
    typer.echo(
        "Before broader public launch, follow `docs/live-validation.md` and record one controlled live-validation run."
    )


@app.command()
def doctor(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit privacy-safe machine-readable diagnostics."),
    ] = False,
) -> None:
    """Check local install, config, scan mode, and storage readiness."""
    checks, exit_code = _doctor_diagnostics(config.expanduser())
    if json_output:
        typer.echo(
            json.dumps(
                _doctor_payload(config.expanduser(), checks, exit_code),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for check in checks:
            typer.echo(f"{check['state']}: {check['label']}: {check['detail']}")
    raise typer.Exit(exit_code)


@app.command("support-bundle")
def support_bundle(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination .zip path."),
    ] = Path("xig-support.zip"),
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the destination if it already exists."),
    ] = False,
) -> None:
    """Create a privacy-safe diagnostic zip for support issues."""
    destination = output.expanduser()
    if destination.exists() and not force:
        typer.echo(
            f"{destination} already exists; pass --force to replace it",
            err=True,
        )
        raise typer.Exit(1)
    if destination.parent != Path("."):
        destination.parent.mkdir(parents=True, exist_ok=True)
    config_path = config.expanduser()
    checks, doctor_exit_code = _doctor_diagnostics(config_path)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": str(config_path),
        "doctor_ok": doctor_exit_code == 0,
        "files": ["SUPPORT_README.md", "doctor.json", "MANIFEST.json"],
        "privacy": "This bundle intentionally excludes config files, tokens, cookies, browser profiles, screenshots, raw report packages, and private evidence.",
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SUPPORT_README.md", _support_bundle_readme())
        archive.writestr(
            "doctor.json",
            json.dumps(
                _doctor_payload(config_path, checks, doctor_exit_code),
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        archive.writestr("MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    typer.echo(f"Support bundle written to {destination}")
    typer.echo("Review before sharing. Do not attach raw reports, cookies, or tokens.")
    if doctor_exit_code != 0:
        typer.echo("Doctor found setup issues; the bundle was still created.")


def _doctor_diagnostics(config_path: Path) -> tuple[list[dict[str, str]], int]:
    failures = 0
    checks: list[dict[str, str]] = []

    def emit(state: str, label: str, detail: str) -> None:
        checks.append({"state": state, "label": label, "detail": detail})

    emit("OK", "python", sys.version.split()[0])

    if importlib.util.find_spec("playwright") is not None:
        emit("OK", "playwright", "Python package is installed")
        browser_path = _chromium_executable_path()
        if browser_path is not None and browser_path.exists():
            emit("OK", "chromium", str(browser_path.expanduser()))
        else:
            emit(
                "WARN",
                "chromium",
                "browser binary not found; run `playwright install chromium` before live scraping or reporting",
            )
    else:
        failures += 1
        emit("FAIL", "playwright", "install package dependencies first")

    if not config_path.exists():
        emit(
            "WARN",
            "config",
            f"{config_path} not found; run `xig scan-fixture` for demo setup or `xig init` for real use",
        )
        return checks, failures

    try:
        cfg = load_config(config_path)
    except (OSError, ValueError, ValidationError) as exc:
        emit("FAIL", "config", str(exc))
        return checks, 1

    emit(
        "OK",
        "config",
        f"{len(cfg.protected_identities)} protected identity configured",
    )
    for warning in _starter_identity_warnings(cfg):
        emit("WARN", "identity", warning)

    try:
        decision = select_scan_mode(cfg)
    except ValueError as exc:
        failures += 1
        emit("FAIL", "scan mode", str(exc))
    else:
        token_state = "token set" if decision.bearer_token else "no token"
        emit(
            "OK",
            "scan mode",
            f"{decision.mode.value} ({decision.reason}; {token_state})",
        )

    token_name = cfg.x_api.bearer_token_env
    emit(
        "OK" if os.getenv(token_name) else "WARN",
        "x api token",
        f"{token_name} is {'set' if os.getenv(token_name) else 'not set'}",
    )

    storage_paths = [
        ("database parent", cfg.storage.db_path.parent),
        ("evidence dir", cfg.storage.evidence_dir),
        ("reports dir", cfg.storage.reports_dir),
    ]
    for label, path in storage_paths:
        if _is_writable_dir(path):
            emit("OK", label, str(path.expanduser()))
        else:
            failures += 1
            emit("FAIL", label, f"{path.expanduser()} is not writable")

    try:
        store = ReviewStore(cfg.storage.db_path)
        pending = sum(
            len(store.list_queue(identity.handle))
            for identity in cfg.protected_identities
        )
    except Exception as exc:
        failures += 1
        emit("FAIL", "sqlite", str(exc))
    else:
        emit("OK", "sqlite", f"review queue reachable; pending={pending}")

    if failures:
        return checks, 1
    return checks, 0


def _doctor_payload(
    config_path: Path, checks: list[dict[str, str]], exit_code: int
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": str(config_path),
        "ok": exit_code == 0,
        "checks": checks,
    }


def _support_bundle_readme() -> str:
    return """# x-impersonation-guard support bundle

This zip is designed for public GitHub issues and maintainer support.

Included:

- `doctor.json`: privacy-safe setup diagnostics from `xig doctor --json`.
- `MANIFEST.json`: bundle metadata.

Not included:

- config files;
- API tokens or environment values;
- cookies or browser profiles;
- screenshots;
- raw report packages;
- private DMs, emails, follower data, or evidence.

Review this archive before sharing it publicly. If you need to share report-package diagnostics, run `xig redact-report <report_dir>` and attach that redacted zip separately.
"""


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
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination file path."),
    ] = None,
) -> None:
    """Export queued candidates."""
    normalized = format.lower()
    if normalized not in {"json", "zip"}:
        raise typer.BadParameter("format must be json or zip")
    cfg = _load(config)
    store = ReviewStore(cfg.storage.db_path)
    payload = _queue_export_payload(store.list_queue())
    if normalized == "json":
        rendered = json.dumps(payload, indent=2, default=str)
        if output is None:
            typer.echo(rendered)
        else:
            destination = output.expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered + "\n")
            typer.echo(f"Exported {len(payload)} queued candidates to {destination}")
        return

    destination = output.expanduser() if output else Path("xig-queue-export.zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "candidate_count": len(payload),
        "format": "xig_queue_export_v1",
        "files": ["queue.json", "EXPORT_MANIFEST.json"],
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("queue.json", json.dumps(payload, indent=2, default=str))
        archive.writestr("EXPORT_MANIFEST.json", json.dumps(manifest, indent=2))
    typer.echo(f"Exported {len(payload)} queued candidates to {destination}")


def _resolve_fixture_path(input_path: Path) -> Path:
    fixture_path = input_path.expanduser()
    if fixture_path.exists():
        return fixture_path
    if input_path == Path("examples/demo_fixture.json"):
        return Path(
            str(files("x_impersonation_guard.resources").joinpath("demo_fixture.json"))
        )
    if not fixture_path.is_absolute():
        source_path = Path(__file__).resolve().parents[2] / fixture_path
        if source_path.exists():
            return source_path
    return fixture_path


def _demo_config() -> AppConfig:
    raw = default_config_dict()
    raw["protected_identities"][0].update(
        {
            "name": "Demo User",
            "handle": "demouser",
            "display_name": "Demo User",
            "user_id": "1000000001",
            "reporter_name": "Demo User",
            "reporter_email": "demo@example.com",
            "extra_handle_variants": [],
            "extra_display_variants": [],
        }
    )
    return AppConfig.model_validate(raw)


def _config_for_demo_fixture(cfg: AppConfig, fixture: FixtureScan) -> AppConfig:
    raw = cfg.model_dump(mode="json")
    raw["protected_identities"][0].update(
        {
            "name": fixture.protected.name,
            "handle": fixture.protected.username,
            "display_name": fixture.protected.name,
            "user_id": fixture.protected.id,
            "reporter_name": fixture.protected.name,
            "reporter_email": "demo@example.com",
            "extra_handle_variants": [],
            "extra_display_variants": [],
        }
    )
    return AppConfig.model_validate(raw)


def _prompt_init_fields(
    *,
    handle: str | None,
    display_name: str | None,
    reporter_name: str | None,
    reporter_email: str | None,
) -> tuple[str, str, str, str]:
    resolved_handle = handle or typer.prompt("Protected X handle")
    resolved_display_name = display_name or typer.prompt("Public display name")
    resolved_reporter_name = reporter_name or typer.prompt(
        "Reporter name",
        default=resolved_display_name,
        show_default=True,
    )
    resolved_reporter_email = reporter_email or typer.prompt(
        "Reporter email for Help Center reports"
    )
    return (
        resolved_handle,
        resolved_display_name,
        resolved_reporter_name,
        resolved_reporter_email,
    )


def _chromium_executable_path() -> Path | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path)
    except Exception:
        return None


def _apply_demo_detection_times(
    store: ReviewStore, identity_handle: str, fixture: DemoFixture
) -> None:
    demo_by_handle = {
        candidate.handle.lower(): candidate for candidate in fixture.demo_candidates
    }
    with store.session_factory() as session:
        rows = session.scalars(
            select(CandidateRecord).where(
                CandidateRecord.identity_handle == identity_handle
            )
        ).all()
        for row in rows:
            demo_candidate = demo_by_handle.get(row.handle.lower())
            if demo_candidate is None:
                continue
            detected_at = datetime.now(UTC) - timedelta(
                hours=demo_candidate.first_detected_hours_ago
            )
            row.created_at = detected_at
            row.updated_at = detected_at
            profile = json.loads(row.profile_json)
            profile.update(
                {
                    "sample_posts": demo_candidate.sample_posts,
                    "candidate_pic": demo_candidate.candidate_pic,
                    "expected_tier": demo_candidate.expected_tier,
                }
            )
            row.profile_json = json.dumps(profile)
            score = json.loads(row.score_breakdown_json or "{}")
            score["protected_profile_image_phash"] = (
                fixture.demo_protected_identity.profile_image_hash
            )
            row.score_breakdown_json = json.dumps(score)
        session.commit()


def _relative_age(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(UTC) - value).total_seconds()))
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    return f"{hours // 24}d"


def _parse_list_status(value: str) -> QueueStatus | None:
    normalized = value.strip().lower().replace("-", "_")
    if normalized == "all":
        return None
    try:
        return QueueStatus(normalized)
    except ValueError as exc:
        allowed = ", ".join([status.value for status in QueueStatus] + ["all"])
        raise typer.BadParameter(f"status must be one of: {allowed}") from exc


def _status_label(status: QueueStatus | None) -> str:
    return status.value if status is not None else "queued"


def _format_queue_counts(counts: dict[str, int]) -> str:
    return " ".join(
        f"{status.value}={counts.get(status.value, 0)}" for status in QueueStatus
    )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _is_writable_dir(path: Path) -> bool:
    directory = path.expanduser()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".xig-write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError:
        return False
    return True


def _echo_commands(commands: list[str]) -> None:
    for command in commands:
        typer.echo(f"  {command}")


def _render_validation_template(config_path: Path, identity_handle: str | None) -> str:
    scope = _command_scope(config_path, identity_handle)
    identity_line = (
        f"@{identity_handle}" if identity_handle else "N/A or single identity"
    )
    generated_at = datetime.now(UTC).isoformat()
    return f"""# X Impersonation Guard live-validation result

Generated: {generated_at}
Config: `{config_path}`
Identity: `{identity_line}`

## Safety rules

- [ ] Do not paste X API tokens, cookies, browser profiles, private DMs, private emails, or unredacted report packages.
- [ ] Do not run live reporting until a candidate has been reviewed, approved, and dry-run evidence has been inspected.
- [ ] Submit at most one controlled live Help Center report for this validation run.
- [ ] Share only redacted diagnostics created with `xig redact-report`.

## Environment

- [ ] Installed package version:
- [ ] Install method: pipx / uvx / source checkout / other:
- [ ] Python version:
- [ ] OS:
- [ ] Browser automation available: yes / no:
- [ ] Token presence checked without printing token: yes / no:

Recommended commands:

```bash
xig doctor {scope}
xig validation-template {scope} --output live-validation-result.md
```

## Calibration

- [ ] Labeled benign and impersonator examples prepared.
- [ ] Calibration command completed.
- [ ] Precision:
- [ ] Recall:
- [ ] F1:
- [ ] False positives:
- [ ] False negatives:
- [ ] Calibration evidence file:

Recommended command:

```bash
xig calibrate {scope} --input labeled-calibration.json --output calibration-results.json
```

## Read-only live scan

- [ ] Scan mode:
- [ ] Configured request budget:
- [ ] Estimated spend:
- [ ] Scan completed without live reports.
- [ ] Candidate count:
- [ ] Pending:
- [ ] Snoozed:
- [ ] Approved:
- [ ] Dismissed:
- [ ] Reported:
- [ ] Failed:
- [ ] Notes on false positives or false negatives:

Recommended commands:

```bash
xig scan {scope}
xig status {scope}
xig status {scope} --json > live-status.json
xig list {scope} --status all
```

## Review and dry-run package

- [ ] Highest-priority candidate reviewed.
- [ ] Candidate ID:
- [ ] Candidate handle:
- [ ] Approval decision:
- [ ] Dry-run package path:
- [ ] Redacted diagnostic zip path:
- [ ] Dry-run package contains no secrets intended for public sharing: yes / no:

Recommended commands:

```bash
xig review {scope} --next
xig review {scope} --approve <candidate_id>
xig report {scope} --dry-run <candidate_id>
xig redact-report <report_dir>
```

## Controlled live report

- [ ] Live report intentionally selected: yes / no:
- [ ] Candidate was approved before live reporting: yes / no:
- [ ] Dry-run evidence was inspected before live reporting: yes / no:
- [ ] Command used `--execute --confirm-live`: yes / no:
- [ ] Help Center selector status: passed / failed:
- [ ] Submission status: submitted / failed / skipped:
- [ ] Report package path:
- [ ] Follow-up needed:

Recommended command only after approval and dry-run review:

```bash
xig report {scope} --execute --confirm-live <candidate_id>
```

## Public launch decision

- [ ] Keep live validation pending.
- [ ] Mark one or more gates verified in `docs/status.md` with evidence.
- [ ] Open a bug with redacted diagnostics.

Summary:
"""


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


def _render_review_queue(records: list[CandidateRecord]) -> None:
    if not records:
        typer.echo("No pending candidates.")
        return
    typer.echo(f"Pending review candidates: {len(records)}")
    typer.echo(
        "Use `xig review --show <id>` for evidence, `xig review --approve <id>` to approve, `xig review --dismiss <id>` to dismiss, or `xig review --snooze <id>` to defer."
    )
    for record in records:
        score = _score_payload(record)
        reasons = score.get("reasons") or []
        reason_text = "; ".join(str(reason) for reason in reasons[:2])
        suffix = f" | {reason_text}" if reason_text else ""
        typer.echo(
            f"{record.id}: @{record.handle} ({record.display_name}) score={record.score} priority={record.priority} detected={_relative_age(record.created_at)}{suffix}"
        )


def _get_review_candidate(
    store: ReviewStore, candidate_id: int, identity_handle: str | None
) -> CandidateRecord:
    record = store.get_candidate(candidate_id)
    if record is None:
        raise typer.BadParameter(f"candidate not found: {candidate_id}")
    if identity_handle is not None and record.identity_handle != identity_handle:
        raise typer.BadParameter(
            f"candidate {candidate_id} does not belong to @{identity_handle}"
        )
    return record


def _next_pending_candidate(
    store: ReviewStore, identity_handle: str | None
) -> CandidateRecord | None:
    records = store.list_queue(identity_handle)
    return records[0] if records else None


def _render_review_detail(
    record: CandidateRecord,
    *,
    config_path: Path = Path("config.yaml"),
    identity_handle: str | None = None,
) -> None:
    profile = _profile_payload(record)
    score = _score_payload(record)
    reasons = [str(reason) for reason in score.get("reasons") or []]
    mitigations = [str(item) for item in score.get("mitigations") or []]
    weighted = score.get("weighted_scores") or {}

    typer.echo(f"Candidate {record.id}: @{record.handle}")
    typer.echo(f"Display name: {record.display_name}")
    typer.echo(f"Protected identity: @{record.identity_handle}")
    typer.echo(f"Profile: https://x.com/{record.handle}")
    typer.echo(
        f"Score: {record.score} | Priority: {record.priority or 'n/a'} | Status: {record.status} | Source: {record.source}"
    )
    typer.echo(f"Detected: {_relative_age(record.created_at)}")
    typer.echo(
        "Account: "
        f"followers={profile.get('followers_count', 0):,} "
        f"following={profile.get('following_count', 0):,} "
        f"posts={profile.get('tweet_count', 0):,} "
        f"verified={profile.get('verified', False)}"
    )
    description = str(profile.get("description") or "").strip()
    if description:
        typer.echo(f"Bio: {description}")
    if reasons:
        typer.echo("Reasons:")
        for reason in reasons:
            typer.echo(f"- {reason}")
    if mitigations:
        typer.echo("Mitigations:")
        for mitigation in mitigations:
            typer.echo(f"- {mitigation}")
    if isinstance(weighted, dict) and weighted:
        typer.echo("Top weighted signals:")
        for name, value in _top_weighted_signals(weighted):
            typer.echo(f"- {name.replace('_', ' ')}: {value:.1f}")
    typer.echo("Next steps:")
    typer.echo(
        f"- Approve: {_review_command('approve', record.id, config_path, identity_handle)}"
    )
    typer.echo(
        f"- Dismiss: {_review_command('dismiss', record.id, config_path, identity_handle)}"
    )
    typer.echo(
        f"- Snooze: {_review_command('snooze', record.id, config_path, identity_handle)}"
    )
    typer.echo(
        f"- Dry-run after approval: {_report_command(record.id, config_path, identity_handle, '--dry-run')}"
    )


def _command_identity_handle(
    cfg: AppConfig,
    selected_identity: Any,
    record: CandidateRecord,
) -> str | None:
    if selected_identity is not None or len(cfg.protected_identities) > 1:
        return record.identity_handle
    return None


def _review_command(
    action: str, candidate_id: int, config_path: Path, identity_handle: str | None
) -> str:
    return f"xig review {_command_scope(config_path, identity_handle)} --{action} {candidate_id}"


def _report_command(
    candidate_id: int, config_path: Path, identity_handle: str | None, mode: str
) -> str:
    return f"xig report {_command_scope(config_path, identity_handle)} {mode} {candidate_id}"


def _command_scope(config_path: Path, identity_handle: str | None) -> str:
    parts = ["--config", shlex.quote(str(config_path.expanduser()))]
    if identity_handle is not None:
        parts.extend(["--identity", shlex.quote(identity_handle)])
    return " ".join(parts)


def _profile_payload(record: CandidateRecord) -> dict[str, Any]:
    try:
        payload = json.loads(record.profile_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _score_payload(record: CandidateRecord) -> dict[str, Any]:
    if not record.score_breakdown_json:
        return {}
    try:
        payload = json.loads(record.score_breakdown_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _top_weighted_signals(weighted: dict[Any, Any]) -> list[tuple[str, float]]:
    signals = []
    for name, value in weighted.items():
        try:
            signals.append((str(name), float(value)))
        except (TypeError, ValueError):
            continue
    return sorted(signals, key=lambda item: item[1], reverse=True)[:5]


SENSITIVE_REPORT_FIELDS = {
    "candidate_handle",
    "description",
    "display_name",
    "handle",
    "id",
    "identity_handle",
    "name",
    "profile_image_url",
    "reporter_email",
    "reporter_name",
    "user_id",
    "username",
    "x_user_id",
}

SENSITIVE_KEY_PATTERNS = (
    "authorization",
    "bearer",
    "cookie",
    "csrf",
    "password",
    "secret",
    "session",
    "token",
)


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>"
            if _is_sensitive_json_key(str(key))
            else _redact_json(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<redacted-email>", value)
        redacted = re.sub(
            r"https?://(?:www\.)?(?:x|twitter)\.com/[A-Za-z0-9_]+",
            "https://x.com/<redacted>",
            redacted,
        )
        return _redact_secret_text(redacted)
    return value


def _redact_text(value: str) -> str:
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<redacted-email>", value)
    redacted = re.sub(
        r"https?://(?:www\.)?(?:x|twitter)\.com/[A-Za-z0-9_]+",
        "https://x.com/<redacted>",
        redacted,
    )
    return _redact_secret_text(redacted)


def _redact_secret_text(value: str) -> str:
    redacted = re.sub(
        r"(?i)\b(authorization)\s*[:=]\s*bearer\s+[^'\"\s,;]+",
        r"\1=<redacted>",
        value,
    )
    redacted = re.sub(
        r"(?i)\bbearer\s+[^'\"\s,;]+",
        "Bearer <redacted>",
        redacted,
    )
    return re.sub(
        r"(?i)\b(bearer|token|authorization|cookie|set-cookie|session|csrf|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+",
        r"\1=<redacted>",
        redacted,
    )


def _is_sensitive_json_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_REPORT_FIELDS or any(
        pattern in normalized for pattern in SENSITIVE_KEY_PATTERNS
    )


def _queue_export_payload(records: list[CandidateRecord]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "identity": record.identity_handle,
            "handle": record.handle,
            "display_name": record.display_name,
            "score": record.score,
            "priority": record.priority,
            "status": record.status,
            "source": record.source,
            "detected_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "profile": _profile_payload(record),
            "score_breakdown": _score_payload(record),
        }
        for record in records
    ]


def _starter_identity_warnings(cfg: AppConfig) -> list[str]:
    warnings = []
    for identity in cfg.protected_identities:
        placeholders = []
        if identity.handle == "yourhandle":
            placeholders.append("handle")
        if identity.display_name == "Your Name":
            placeholders.append("display_name")
        if identity.reporter_name == "Your Name":
            placeholders.append("reporter_name")
        if str(identity.reporter_email) == "you@example.com":
            placeholders.append("reporter_email")
        if placeholders:
            warnings.append(
                f"@{identity.handle} still uses starter values for {', '.join(placeholders)}; run `xig init --guided` or edit config.yaml before live scans"
            )
    return warnings


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
