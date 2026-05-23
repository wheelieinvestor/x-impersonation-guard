from x_impersonation_guard.clients.x_scrape import _playwright_install_help


def test_playwright_install_help_points_to_docs() -> None:
    message = _playwright_install_help("browser executable does not exist")
    assert "playwright install chromium" in message
    assert "/install/#playwright-browser-install-failures" in message
    assert "browser executable does not exist" in message
