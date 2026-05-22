"""Textual review queue."""

from __future__ import annotations

import json
import webbrowser
from datetime import UTC, datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from x_impersonation_guard.models import QueueStatus
from x_impersonation_guard.storage.models import CandidateRecord
from x_impersonation_guard.storage.repository import ReviewStore
from x_impersonation_guard.utils.image_hash import hamming_distance

TIER_STYLE = {
    "critical": ("🚨", "critical"),
    "high": ("⚠", "high"),
    "medium": ("·", "medium"),
    "low": ("", "low"),
    None: ("", "filtered"),
}


class ReviewQueueApp(App[None]):
    CSS = """
    Screen {
        background: #080b12;
        color: #d7dde8;
    }

    #shell {
        height: 1fr;
        padding: 1;
    }

    #summary {
        height: 3;
        padding: 0 1;
        background: #101622;
        border: solid #263246;
        color: #edf2f7;
    }

    #body {
        height: 1fr;
        margin-top: 1;
    }

    #list {
        width: 42;
        height: 1fr;
        padding: 1;
        background: #0d111a;
        border: solid #263246;
    }

    #detail {
        width: 1fr;
        height: 1fr;
        margin-left: 1;
        padding: 1 2;
        background: #0d111a;
        border: solid #263246;
    }

    #notice {
        height: 3;
        margin-top: 1;
        padding: 0 1;
        background: #101622;
        border: solid #263246;
        color: #b9c8ff;
    }

    .row {
        height: 1;
        padding: 0 1;
        color: #9aa8bd;
    }

    .selected {
        background: #182237;
        color: #ffffff;
        text-style: bold;
    }

    .critical {
        color: #ff5d73;
    }

    .high {
        color: #ffb454;
    }

    .medium {
        color: #ffd866;
    }

    .low, .filtered {
        color: #6b7280;
    }
    """

    BINDINGS = [
        ("up,k", "cursor_up", "Up"),
        ("down,j", "cursor_down", "Down"),
        ("a", "approve", "Approve"),
        ("d", "dismiss", "Dismiss"),
        ("s", "snooze", "Snooze"),
        ("o", "open_profile", "Open"),
        ("r", "refresh_queue", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    selected_index: reactive[int] = reactive(0)

    def __init__(self, store: ReviewStore) -> None:
        super().__init__()
        self.store = store
        self.records: list[CandidateRecord] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="shell"):
            yield Static(id="summary")
            with Horizontal(id="body"):
                yield Vertical(id="list")
                yield Static(id="detail")
            yield Static(id="notice")
        yield Footer()

    def on_mount(self) -> None:
        self._load_records()
        self._render_all(
            "Review queue loaded. Use j/k to move, a to approve, s to snooze."
        )

    def action_refresh_queue(self) -> None:
        self._load_records()
        self.selected_index = min(self.selected_index, max(0, len(self.records) - 1))
        self._render_all("Refreshed review queue.")

    def action_cursor_up(self) -> None:
        if not self.records:
            return
        self.selected_index = max(0, self.selected_index - 1)
        self._render_all()

    def action_cursor_down(self) -> None:
        if not self.records:
            return
        self.selected_index = min(len(self.records) - 1, self.selected_index + 1)
        self._render_all()

    def action_approve(self) -> None:
        if not self.records:
            return
        record = self.records[self.selected_index]
        self.store.set_status(record.id, QueueStatus.APPROVED)
        self._load_records()
        self.selected_index = min(self.selected_index, max(0, len(self.records) - 1))
        self._render_all(
            f"Approved @{record.handle}. Dry-run or submit from `xig report {record.id}`."
        )

    def action_dismiss(self) -> None:
        if not self.records:
            return
        record = self.records[self.selected_index]
        self.store.set_status(record.id, QueueStatus.DISMISSED)
        self._load_records()
        self.selected_index = min(self.selected_index, max(0, len(self.records) - 1))
        self._render_all(f"Dismissed @{record.handle}.")

    def action_snooze(self) -> None:
        if not self.records:
            return
        record = self.records[self.selected_index]
        self.store.set_status(record.id, QueueStatus.SNOOZED)
        self._load_records()
        self.selected_index = min(self.selected_index, max(0, len(self.records) - 1))
        self._render_all(
            f"Snoozed @{record.handle}. Restore later with `xig review --restore {record.id}`."
        )

    def action_open_profile(self) -> None:
        if not self.records:
            return
        record = self.records[self.selected_index]
        profile = _profile_payload(record)
        url = str(profile.get("handle_url") or f"https://x.com/{record.handle}")
        opened = webbrowser.open(url)
        if opened:
            self._render_all(f"Opened @{record.handle}: {url}")
        else:
            self._render_all(f"Open manually: {url}")

    def _load_records(self) -> None:
        self.records = self.store.list_queue()

    def _render_all(self, notice: str | None = None) -> None:
        self.query_one("#summary", Static).update(self._summary())
        self._render_list()
        self.query_one("#detail", Static).update(self._detail())
        if notice is not None:
            self.query_one("#notice", Static).update(notice)

    def _summary(self) -> str:
        counts = {key: 0 for key in ("critical", "high", "medium", "low")}
        for record in self.records:
            if record.priority in counts:
                counts[record.priority] += 1
        return (
            "[b]x-impersonation-guard[/b]  review queue  "
            f"candidates={len(self.records)}  "
            f"[critical]critical={counts['critical']}[/]  "
            f"[high]high={counts['high']}[/]  "
            f"[medium]medium={counts['medium']}[/]  "
            f"[low]low={counts['low']}[/]"
        )

    def _render_list(self) -> None:
        container = self.query_one("#list", Vertical)
        container.remove_children()
        if not self.records:
            container.mount(Static("No candidates yet. Run `xig scan` to start."))
            return
        for index, record in enumerate(self.records):
            icon, tier_class = TIER_STYLE.get(record.priority, ("", "filtered"))
            marker = "▌" if index == self.selected_index else " "
            row = Static(
                f"{marker} {icon} @{record.handle} · {record.score or 0} · {_relative_age(record.created_at)}",
                classes=f"row {tier_class} {'selected' if index == self.selected_index else ''}",
            )
            container.mount(row)

    def _detail(self) -> str:
        if not self.records:
            return "No candidates yet. Run `xig scan-fixture` for the offline demo."
        record = self.records[self.selected_index]
        profile = _profile_payload(record)
        score = _score_payload(record)
        candidate_hash = profile.get("profile_image_phash")
        protected_hash = _protected_hash_from_score(score)
        distance = hamming_distance(candidate_hash, protected_hash)
        distance_label = "n/a" if distance is None else f"{64 - distance}/64"
        posts = profile.get("sample_posts") or []
        pic = profile.get("candidate_pic") or []
        handle = profile.get("username", record.handle)
        display_name = profile.get("name", record.display_name)
        description = profile.get("description", "")
        lines = [
            f"[b]@{handle}[/b]  {display_name}",
            f"{handle} vs protected identity  ({_handle_diff_hint(handle)})",
            "",
            f"Score: [{record.priority or 'low'}]{record.score or 0}[/]  Priority: {record.priority or 'filtered'}  Detected: {_relative_age(record.created_at)}",
            f"Profile image similarity: {_bar((64 - distance) / 64 if distance is not None else 0)}  {distance_label}",
            "",
            "[b]Profile[/b]",
            _indent_art(pic) if pic else "  no profile art",
            "",
            "[b]Bio[/b]",
            f"  {_highlight_identity(description)}",
            "",
            "[b]Account[/b]",
            f"  followers={profile.get('followers_count', 0):,}  verified={profile.get('verified', False)}  status={record.status}",
            "",
            "[b]Signal breakdown[/b]",
            _signal_bars(score),
            "",
            "[b]Sample post[/b]",
            f"  {posts[0] if posts else 'No sample post in fixture.'}",
            "",
            "Open profile: o  Approve: a  Dismiss: d  Snooze: s",
        ]
        return "\n".join(lines)


def _profile_payload(record: CandidateRecord) -> dict[str, Any]:
    payload = json.loads(record.profile_json)
    return payload if isinstance(payload, dict) else {}


def _score_payload(record: CandidateRecord) -> dict[str, Any]:
    if not record.score_breakdown_json:
        return {}
    payload = json.loads(record.score_breakdown_json)
    return payload if isinstance(payload, dict) else {}


def _protected_hash_from_score(score: dict[str, Any]) -> str | None:
    return score.get("protected_profile_image_phash")


def _signal_bars(score: dict[str, Any]) -> str:
    weighted = score.get("weighted_scores") or {}
    if not weighted:
        return "  no score breakdown"
    rows = []
    for name, value in weighted.items():
        rows.append(
            f"  {name.replace('_', ' '):24} {_bar(float(value) / 25)} {value:4.1f}"
        )
    return "\n".join(rows)


def _bar(value: float, width: int = 14) -> str:
    value = max(0.0, min(1.0, value))
    filled = round(value * width)
    return "█" * filled + "░" * (width - filled)


def _handle_diff_hint(handle: str) -> str:
    clean = handle.replace("_", "")
    if clean.endswith("1"):
        return "1-char suffix"
    if "official" in handle:
        return "official suffix"
    if "giveaway" in handle:
        return "promo suffix"
    return "similar handle"


def _highlight_identity(value: str) -> str:
    return (
        value.replace("Alex Charts", "[b]Alex Charts[/b]")
        .replace("alex_charts", "[b]alex_charts[/b]")
        .replace("@alex_charts", "[@alex_charts]")
    )


def _indent_art(lines: list[str]) -> str:
    return "\n".join(f"  {line}" for line in lines)


def _relative_age(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(UTC) - value).total_seconds()))
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"
