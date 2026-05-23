from x_impersonation_guard.i18n import t


def test_i18n_returns_english_by_default() -> None:
    assert "first run" in t("first_run")


def test_i18n_supports_sample_spanish_strings() -> None:
    assert "No hay candidatos" in t("no_pending_candidates", locale="es")


def test_i18n_falls_back_to_english_for_unknown_locale() -> None:
    assert t("no_pending_candidates", locale="fr") == t("no_pending_candidates")
