from __future__ import annotations

import tomllib
from pathlib import Path


def test_package_metadata_is_public_launch_ready() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]

    assert project["name"] == "x-impersonation-guard"
    assert "impersonation" in project["keywords"]
    assert "security" in project["keywords"]
    assert "creator-tools" in project["keywords"]
    assert "Topic :: Security" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert Path("src/x_impersonation_guard/py.typed").exists()

    urls = project["urls"]
    assert urls["Documentation"].startswith("https://")
    assert urls["Issues"].endswith("/issues")
    assert urls["Source"].endswith("/x-impersonation-guard")


def test_launch_copy_has_no_internal_placeholders() -> None:
    launch_text = "\n".join(
        path.read_text() for path in sorted(Path("launch").glob("*.md"))
    )

    assert "Dean will fill in" not in launch_text
    assert "replace this" not in launch_text
    assert "TBD" not in launch_text
