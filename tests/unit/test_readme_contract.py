from pathlib import Path


def test_readme_names_non_default_limits() -> None:
    readme = Path("README.md").read_text()
    assert "## What this tool does NOT do" in readme
    assert "does not submit reports through the X API" in readme
    assert "does not bypass X rate limits" in readme
    assert "does not yet provide a hosted SaaS dashboard" in readme
