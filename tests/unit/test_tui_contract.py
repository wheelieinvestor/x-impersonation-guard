from __future__ import annotations

from pathlib import Path

from x_impersonation_guard.review.tui import ReviewQueueApp


def test_review_tui_exposes_snooze_binding() -> None:
    bindings: dict[str, str] = {}
    for binding in ReviewQueueApp.BINDINGS:
        if isinstance(binding, tuple):
            bindings[binding[0]] = binding[1]
        else:
            bindings[binding.key] = binding.action

    assert bindings["s"] == "snooze"
    assert bindings["o"] == "open_profile"


def test_review_tui_preserves_config_and_identity_scope() -> None:
    app = ReviewQueueApp(
        store=object(),  # type: ignore[arg-type]
        config_path=Path("custom.yaml"),
        identity_handle="firstcreator",
    )

    assert app.identity_handle == "firstcreator"
    assert app._review_command(42, "--restore") == (
        "xig review --config custom.yaml --identity firstcreator --restore 42"
    )
    assert app._report_command(42, "--dry-run") == (
        "xig report --config custom.yaml --identity firstcreator --dry-run 42"
    )
