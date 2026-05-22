"""Playwright scrape fallback."""

from __future__ import annotations

import re

from playwright.async_api import async_playwright

from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import AccountProfile


class XScrapeClient(XProfileLookup):
    def __init__(self, user_data_dir: str, headless: bool = False) -> None:
        self.user_data_dir = user_data_dir
        self.headless = headless

    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
            )
            page = await context.new_page()
            response = await page.goto(
                f"https://x.com/{username}", wait_until="domcontentloaded"
            )
            if response is None or response.status >= 400:
                await context.close()
                return None
            title = await page.title()
            html = await page.content()
            await context.close()
        name = title.split("(")[0].strip() or username
        description = _meta_description(html)
        return AccountProfile(
            id=username, username=username, name=name, description=description
        )

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        del display_name
        return []

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        del user_id, limit
        return []


def _meta_description(html: str) -> str:
    match = re.search(r'<meta name="description" content="([^"]*)"', html)
    return match.group(1) if match else ""
