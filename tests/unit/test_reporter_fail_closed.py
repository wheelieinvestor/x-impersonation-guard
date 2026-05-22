from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.models import AccountProfile
from x_impersonation_guard.reporters.x_help_form import (
    FieldRef,
    IncompleteFormError,
    RequiredFieldNotFoundError,
    XHelpFormReporter,
    _fill_first_matching,
)


class FakeLocator:
    def __init__(self, count: int = 0, value: str = "") -> None:
        self._count = count
        self.value = value
        self.clicked = False

    async def count(self) -> int:
        return self._count

    @property
    def first(self) -> FakeLocator:
        return self

    async def fill(self, value: str) -> None:
        self.value = value

    async def input_value(self) -> str:
        return self.value

    async def text_content(self) -> str | None:
        return self.value

    async def click(self) -> None:
        self.clicked = True


class FakePage:
    def __init__(self, labels: dict[str, FakeLocator] | None = None) -> None:
        self.labels = labels or {}
        self.submit = FakeLocator(count=1)
        self.screenshots: list[Path] = []

    def get_by_label(self, label: str, exact: bool = False) -> FakeLocator:
        del exact
        return self.labels.get(label, FakeLocator())

    def get_by_text(self, text: str, exact: bool = False) -> FakeLocator:
        del text, exact
        return FakeLocator()

    def get_by_role(self, role: str, name: str) -> FakeLocator:
        del role, name
        return self.submit

    async def goto(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def screenshot(self, path: Path, full_page: bool = True) -> None:
        del full_page
        self.screenshots.append(path)
        path.write_text("fake screenshot")

    async def content(self) -> str:
        return "<html><body>fake page</body></html>"


@pytest.mark.asyncio
async def test_fill_first_matching_raises_for_required_missing() -> None:
    page = FakePage()

    with pytest.raises(RequiredFieldNotFoundError) as excinfo:
        await _fill_first_matching(
            cast(Any, page), ["Missing", "Also missing"], "value", "email"
        )

    assert excinfo.value.field_name == "email"
    assert excinfo.value.attempted_selectors == ["Missing", "Also missing"]


@pytest.mark.asyncio
async def test_fill_first_matching_allows_optional_missing() -> None:
    page = FakePage()

    await _fill_first_matching(
        cast(Any, page), ["Optional missing"], "value", "optional", required=False
    )


@pytest.mark.asyncio
async def test_verify_all_required_fields_filled_lists_empty_fields(
    tmp_path: Path,
) -> None:
    reporter = XHelpFormReporter(tmp_path, tmp_path, tmp_path)
    page = FakePage(
        {
            "Name": FakeLocator(count=1, value="Dean"),
            "Email": FakeLocator(count=1, value=""),
        }
    )

    with pytest.raises(IncompleteFormError) as excinfo:
        await reporter._verify_all_required_fields_filled(
            cast(Any, page),
            [
                FieldRef("reporter_name", ["Name"]),
                FieldRef("reporter_email", ["Email"]),
            ],
        )

    assert "reporter_email" in str(excinfo.value)
    assert "reporter_name" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_missing_required_field_aborts_before_submit_and_saves_dump(
    tmp_path: Path,
) -> None:
    reporter = XHelpFormReporter(tmp_path, tmp_path, tmp_path, dry_run=False)
    page = FakePage(
        {
            "Your full name": FakeLocator(count=1),
            "Email": FakeLocator(count=1),
        }
    )

    identity = ProtectedIdentity(
        name="Dean Ahrens",
        handle="wheelieinvestor",
        display_name="Wheelie Investor",
        report_as="Me or someone I am authorized to represent",
        reporter_name="Dean Ahrens",
        reporter_email="dean@example.com",
    )
    candidate = AccountProfile(id="2", username="fake", name="Fake")

    with pytest.raises(RequiredFieldNotFoundError):
        await reporter._submit_form(
            cast(Any, page),
            identity=identity,
            candidate=candidate,
            report_dir=tmp_path,
        )

    assert page.submit.clicked is False
    await reporter._save_diagnostic_dump(
        cast(Any, page),
        tmp_path / "20260522_fake",
        RequiredFieldNotFoundError("x", ["y"]),
    )
    failed_dir = tmp_path / "20260522_fake_FAILED"
    assert (failed_dir / "failure_screenshot.png").exists()
    assert (failed_dir / "failure_page.html").exists()
    assert (failed_dir / "failure_diagnostic.json").exists()
