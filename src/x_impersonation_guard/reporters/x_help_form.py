"""X Help Center Playwright reporter.

Selectors are centralized here because help.x.com changes UI markup often.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import structlog
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.models import AccountProfile, ReportMetadata, ScoreResult
from x_impersonation_guard.reporters.base import Reporter, ReportResult

IMPERSONATION_FORM_URL = "https://help.x.com/en/forms/authenticity/impersonation"
logger = structlog.get_logger(__name__)


class ReporterError(RuntimeError):
    """Base reporter failure."""


class RequiredFieldNotFoundError(ReporterError):
    """Raised when a required form field cannot be located."""

    def __init__(self, field_name: str, attempted_selectors: list[str]):
        self.field_name = field_name
        self.attempted_selectors = attempted_selectors
        super().__init__(
            f"Required field '{field_name}' not found. "
            f"Attempted {len(attempted_selectors)} selectors. "
            "X may have changed the form. Submission aborted."
        )


class IncompleteFormError(ReporterError):
    """Raised when required fields are empty before final submit."""


@dataclass(frozen=True)
class FieldRef:
    name: str
    selectors: list[str]


class XHelpFormSelectors:
    issue_text = "I'd like to report impersonation on X"
    submit_name = "Submit"


class SupportsFieldState(Protocol):
    async def count(self) -> int: ...
    @property
    def first(self) -> SupportsFieldState: ...
    async def input_value(self) -> str: ...
    async def text_content(self) -> str | None: ...


class XHelpFormReporter(Reporter):
    def __init__(
        self,
        reports_dir: Path,
        evidence_dir: Path,
        user_data_dir: Path,
        headless: bool = False,
        dry_run: bool = True,
    ) -> None:
        self.reports_dir = reports_dir.expanduser()
        self.evidence_dir = evidence_dir.expanduser()
        self.user_data_dir = user_data_dir.expanduser()
        self.headless = headless
        self.dry_run = dry_run

    async def submit(
        self,
        identity: ProtectedIdentity,
        candidate_id: int,
        candidate: AccountProfile,
        score: ScoreResult,
    ) -> ReportResult:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_dir = self.reports_dir / f"{timestamp}_{candidate.username}"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "score_breakdown.json").write_text(
            score.model_dump_json(indent=2)
        )
        metadata = ReportMetadata(
            candidate_id=candidate_id,
            identity_handle=identity.handle,
            candidate_handle=candidate.username,
            filed_at=datetime.now(UTC),
            reporter_name=identity.reporter_name,
            reporter_email=str(identity.reporter_email),
            reasons=score.reasons,
            score_breakdown=score.model_dump(mode="json"),
        )
        (report_dir / "report.json").write_text(metadata.model_dump_json(indent=2))

        if self.dry_run:
            (report_dir / "evidence_profile.png").write_text(
                "dry-run profile screenshot"
            )
            (report_dir / "evidence_profile.html").write_text(
                f"<html><body>dry run profile @{candidate.username}</body></html>"
            )
            (report_dir / "form_submission.png").write_text(
                "dry-run form submission screenshot"
            )
            (report_dir / "form_response.html").write_text(
                "<html><body>dry run</body></html>"
            )
            return ReportResult(False, report_dir, "dry-run evidence package created")

        page: Page | None = None
        try:
            async with async_playwright() as playwright:
                try:
                    context = await playwright.chromium.launch_persistent_context(
                        str(self.user_data_dir),
                        headless=self.headless,
                    )
                except PlaywrightError as exc:
                    raise ReporterError(_playwright_install_help(str(exc))) from exc
                page = await context.new_page()
                await self._capture_profile(page, candidate, report_dir)
                await self._submit_form(page, identity, candidate, report_dir)
                await context.close()
        except Exception as exc:
            await self._save_diagnostic_dump(page, report_dir, exc)
            logger.error(
                "report_submission_failed",
                report_dir=str(report_dir),
                candidate=candidate.username,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        return ReportResult(True, report_dir, "submitted through X Help Center")

    async def _capture_profile(
        self,
        page: Page,
        candidate: AccountProfile,
        report_dir: Path,
    ) -> None:
        await page.goto(candidate.handle_url, wait_until="domcontentloaded")
        await page.screenshot(path=report_dir / "evidence_profile.png", full_page=True)
        (report_dir / "evidence_profile.html").write_text(await page.content())

    async def _submit_form(
        self,
        page: Page,
        identity: ProtectedIdentity,
        candidate: AccountProfile,
        report_dir: Path,
    ) -> None:
        await page.goto(IMPERSONATION_FORM_URL, wait_until="domcontentloaded")
        await _click_text_if_present(page, XHelpFormSelectors.issue_text)
        required_fields = [
            FieldRef("reporter_name", ["Your full name", "Name"]),
            FieldRef("reporter_email", ["Email", "Email address"]),
            FieldRef(
                "impersonating_account",
                ["Impersonating account", "Account being reported", "Username"],
            ),
            FieldRef(
                "legitimate_account",
                ["Legitimate account", "Account being impersonated"],
            ),
            FieldRef(
                "description",
                ["Description", "Tell us more", "How is this account impersonating"],
            ),
        ]
        await _fill_first_matching(
            page,
            required_fields[0].selectors,
            identity.reporter_name,
            required_fields[0].name,
        )
        await _fill_first_matching(
            page,
            required_fields[1].selectors,
            str(identity.reporter_email),
            required_fields[1].name,
        )
        await _fill_first_matching(
            page,
            required_fields[2].selectors,
            candidate.handle_url,
            required_fields[2].name,
        )
        await _fill_first_matching(
            page,
            required_fields[3].selectors,
            f"https://x.com/{identity.handle}",
            required_fields[3].name,
        )
        description = {
            "reason": "Account appears to impersonate the protected identity.",
            "candidate": candidate.model_dump(mode="json"),
        }
        await _fill_first_matching(
            page,
            required_fields[4].selectors,
            json.dumps(description),
            required_fields[4].name,
        )
        await self._verify_all_required_fields_filled(page, required_fields)
        await page.screenshot(path=report_dir / "form_submission.png", full_page=True)
        (report_dir / "form_response.html").write_text(await page.content())
        submit = page.get_by_role("button", name=XHelpFormSelectors.submit_name)
        if await submit.count() == 0:
            raise RequiredFieldNotFoundError(
                "submit_button", [XHelpFormSelectors.submit_name]
            )
        await submit.first.click()

    async def _verify_all_required_fields_filled(
        self, page: Page, required_fields: list[FieldRef]
    ) -> None:
        """Raise if any required field is empty before submission."""
        empty = [
            field.name
            for field in required_fields
            if not await self._field_has_value(page, field)
        ]
        if empty:
            raise IncompleteFormError(
                f"Refusing to submit: required fields empty: {empty}. "
                "This usually means a selector changed. Re-run with --dry-run to debug."
            )

    async def _field_has_value(self, page: Page, field: FieldRef) -> bool:
        for selector in field.selectors:
            locator = page.get_by_label(selector, exact=False)
            if await locator.count() == 0:
                continue
            first = locator.first
            try:
                value = await first.input_value()
            except Exception:
                text = await first.text_content()
                value = text or ""
            return bool(value.strip())
        return False

    async def _save_diagnostic_dump(
        self, page: Page | None, report_dir: Path, exc: Exception
    ) -> None:
        failed_dir = report_dir.parent / f"{report_dir.name}_FAILED"
        failed_dir.mkdir(parents=True, exist_ok=True)
        if page is not None:
            try:
                await page.screenshot(
                    path=failed_dir / "failure_screenshot.png", full_page=True
                )
                (failed_dir / "failure_page.html").write_text(await page.content())
            except Exception as dump_exc:
                (failed_dir / "diagnostic_dump_error.txt").write_text(str(dump_exc))
        diagnostic = {
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (failed_dir / "failure_diagnostic.json").write_text(
            json.dumps(diagnostic, indent=2)
        )


async def _click_text_if_present(page: Page, text: str) -> None:
    locator = page.get_by_text(text, exact=False)
    if await locator.count() > 0:
        await locator.first.click()


async def _fill_first_matching(
    page: Page,
    labels: list[str],
    value: str,
    field_name: str = "field",
    required: bool = True,
) -> None:
    for label in labels:
        locator = page.get_by_label(label, exact=False)
        if await locator.count() > 0:
            await locator.first.fill(value)
            return
    if required:
        raise RequiredFieldNotFoundError(field_name, labels)


def _playwright_install_help(error: str) -> str:
    return (
        "Playwright Chromium could not start. Run `playwright install chromium` "
        "and see https://wheelieinvestor.github.io/x-impersonation-guard/install/"
        "#playwright-browser-install-failures. "
        f"Original error: {error}"
    )
