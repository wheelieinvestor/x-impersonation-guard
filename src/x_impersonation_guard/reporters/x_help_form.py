"""X Help Center Playwright reporter.

Selectors are centralized here because help.x.com changes UI markup often.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Page, async_playwright

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.models import AccountProfile, ReportMetadata, ScoreResult
from x_impersonation_guard.reporters.base import Reporter, ReportResult

IMPERSONATION_FORM_URL = "https://help.x.com/en/forms/authenticity/impersonation"


class XHelpFormSelectors:
    issue_text = "I'd like to report impersonation on X"
    submit_name = "Submit"


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
            (report_dir / "form_response.html").write_text(
                "<html><body>dry run</body></html>"
            )
            return ReportResult(False, report_dir, "dry-run evidence package created")

        try:
            async with async_playwright() as playwright:
                context = await playwright.chromium.launch_persistent_context(
                    str(self.user_data_dir),
                    headless=self.headless,
                )
                page = await context.new_page()
                await self._capture_profile(page, candidate, report_dir)
                await self._submit_form(page, identity, candidate, report_dir)
                await context.close()
        except Exception as exc:
            (report_dir / "error.txt").write_text(str(exc))
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
        await _fill_first_matching(
            page, ["Your full name", "Name"], identity.reporter_name
        )
        await _fill_first_matching(
            page, ["Email", "Email address"], str(identity.reporter_email)
        )
        await _fill_first_matching(
            page,
            ["Impersonating account", "Account being reported", "Username"],
            candidate.handle_url,
        )
        await _fill_first_matching(
            page,
            ["Legitimate account", "Account being impersonated"],
            f"https://x.com/{identity.handle}",
        )
        description = {
            "reason": "Account appears to impersonate the protected identity.",
            "candidate": candidate.model_dump(mode="json"),
        }
        await _fill_first_matching(
            page,
            ["Description", "Tell us more", "How is this account impersonating"],
            json.dumps(description),
        )
        await page.screenshot(path=report_dir / "form_submission.png", full_page=True)
        (report_dir / "form_response.html").write_text(await page.content())
        submit = page.get_by_role("button", name=XHelpFormSelectors.submit_name)
        if await submit.count() > 0:
            await submit.first.click()


async def _click_text_if_present(page: Page, text: str) -> None:
    locator = page.get_by_text(text, exact=False)
    if await locator.count() > 0:
        await locator.first.click()


async def _fill_first_matching(page: Page, labels: list[str], value: str) -> None:
    for label in labels:
        locator = page.get_by_label(label, exact=False)
        if await locator.count() > 0:
            await locator.first.fill(value)
            return
