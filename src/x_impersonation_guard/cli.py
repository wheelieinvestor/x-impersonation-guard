"""Typer CLI."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
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
            lookup = XApiClient(decision.bearer_token)
        else:
            lookup = XScrapeClient(
                str(Path("~/.x-impersonation-guard/browser").expanduser()),
                headless=cfg.reporting.headless,
            )
    results = asyncio.run(run_scan(cfg, selected, lookup, store))
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
    approve: Annotated[int | None, typer.Option("--approve")] = None,
    dismiss: Annotated[int | None, typer.Option("--dismiss")] = None,
    tui: Annotated[bool, typer.Option("--tui/--no-tui")] = False,
) -> None:
    """Approve, dismiss, or open the review queue."""
    cfg = _load(config)
    selected = cfg.identity_for_handle(identity) if identity else None
    store = ReviewStore(cfg.storage.db_path)
    if show is not None:
        record = _get_review_candidate(
            store, show, selected.handle if selected else None
        )
        _render_review_detail(record)
        return
    if approve is not None:
        _get_review_candidate(store, approve, selected.handle if selected else None)
        store.set_status(approve, QueueStatus.APPROVED)
        typer.echo(f"Approved candidate {approve}")
        return
    if dismiss is not None:
        _get_review_candidate(store, dismiss, selected.handle if selected else None)
        store.set_status(dismiss, QueueStatus.DISMISSED)
        typer.echo(f"Dismissed candidate {dismiss}")
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
    store = ReviewStore(cfg.storage.db_path)
    record = store.get_candidate(candidate_id)
    if record is None:
        raise typer.BadParameter(f"candidate not found: {candidate_id}")
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
    try:
        result = asyncio.run(reporter.submit(identity, candidate_id, candidate, score))
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
                archive.write(path, path.name)
                included.append(path.name)
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
def doctor(
    config: Annotated[Path, typer.Option("--config")] = Path("config.yaml"),
) -> None:
    """Check local install, config, scan mode, and storage readiness."""
    failures = 0

    def emit(state: str, label: str, detail: str) -> None:
        typer.echo(f"{state}: {label}: {detail}")

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

    config_path = config.expanduser()
    if not config_path.exists():
        emit(
            "WARN",
            "config",
            f"{config_path} not found; run `xig scan-fixture` for demo setup or `xig init` for real use",
        )
        raise typer.Exit(failures)

    try:
        cfg = load_config(config_path)
    except (OSError, ValueError, ValidationError) as exc:
        emit("FAIL", "config", str(exc))
        raise typer.Exit(1) from exc

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
        raise typer.Exit(1)


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
        "Use `xig review --show <id>` for evidence, `xig review --approve <id>` to approve, or `xig review --dismiss <id>` to dismiss."
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


def _render_review_detail(record: CandidateRecord) -> None:
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
    typer.echo(f"- Approve: xig review --approve {record.id}")
    typer.echo(f"- Dismiss: xig review --dismiss {record.id}")
    typer.echo(f"- Dry-run after approval: xig report --dry-run {record.id}")


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


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>"
            if str(key) in SENSITIVE_REPORT_FIELDS
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
        return redacted
    return value


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
