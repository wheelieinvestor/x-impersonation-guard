from __future__ import annotations

from pathlib import Path

import yaml


def test_dependabot_tracks_uv_and_github_actions() -> None:
    config = yaml.safe_load(Path(".github/dependabot.yml").read_text())

    ecosystems = {entry["package-ecosystem"] for entry in config["updates"]}
    assert ecosystems == {"uv", "github-actions"}
    for entry in config["updates"]:
        assert entry["directory"] == "/"
        assert entry["schedule"]["interval"] == "weekly"
        assert entry["open-pull-requests-limit"] <= 5


def test_dependency_review_blocks_high_severity_and_copyleft() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/dependency-review.yml").read_text()
    )

    assert workflow["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
    }
    steps = workflow["jobs"]["dependency-review"]["steps"]
    review_step = next(
        step
        for step in steps
        if step.get("uses") == "actions/dependency-review-action@v4"
    )
    assert review_step["with"]["fail-on-severity"] == "high"
    assert "AGPL-3.0" in review_step["with"]["deny-licenses"]
