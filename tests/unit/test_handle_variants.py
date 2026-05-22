from x_impersonation_guard.utils.handle_variants import generate_handle_variants


def test_generate_handle_variants_includes_required_patterns() -> None:
    variants = generate_handle_variants("wheelie")
    assert "real_wheelie" in variants
    assert "wheelie1" in variants
    assert "wheeli" in variants


def test_generate_handle_variants_filters_invalid_long_handles() -> None:
    variants = generate_handle_variants("wheelieinvestor")
    assert "wheelieinvestor1" not in variants
    assert "wheelieinvesto" in variants


def test_generate_handle_variants_includes_confusables() -> None:
    variants = generate_handle_variants("wheelie")
    assert "whee1ie" in variants
    assert "vvheelie" in variants


def test_extra_globs_are_expanded_and_filtered() -> None:
    variants = generate_handle_variants("wheelie", ["wheelie_*", "bad-handle"])
    assert "wheelie_real" in variants
    assert "bad-handle" not in variants
