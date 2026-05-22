"""Typer CLI."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """X impersonation detection and reporting."""
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
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--execute",
            help="Create evidence only or submit the live Help Center form.",
        ),
    ] = True,
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
