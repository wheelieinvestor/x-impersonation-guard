"""Minimal Textual review app placeholder.

The CLI exposes the same approve, dismiss, and list workflow for environments where a
full terminal UI is not desired.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header

from x_impersonation_guard.storage.repository import ReviewStore


class ReviewQueueApp(App[None]):
    def __init__(self, store: ReviewStore) -> None:
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        table: DataTable[str] = DataTable()
        table.add_columns("ID", "Handle", "Score", "Priority", "Status")
        for record in self.store.list_queue():
            table.add_row(
                str(record.id),
                f"@{record.handle}",
                str(record.score or 0),
                record.priority or "",
                record.status,
            )
        yield table
