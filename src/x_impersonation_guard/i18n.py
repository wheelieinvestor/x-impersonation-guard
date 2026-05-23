"""Tiny translation boundary for future CLI localization."""

from __future__ import annotations

DEFAULT_LOCALE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "first_run": "It looks like this is your first run. Try `xig scan-fixture` for an offline demo, or `xig init` to set up against your real account.",
        "no_pending_candidates": "No pending candidates.",
    },
    "es": {
        "first_run": "Parece que esta es tu primera ejecucion. Prueba `xig scan-fixture` para una demo sin conexion, o `xig init` para configurar tu cuenta real.",
        "no_pending_candidates": "No hay candidatos pendientes.",
    },
}


def t(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Return a translated string, falling back to English."""
    return TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE]).get(
        key,
        TRANSLATIONS[DEFAULT_LOCALE][key],
    )
