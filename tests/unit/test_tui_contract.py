from __future__ import annotations

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
