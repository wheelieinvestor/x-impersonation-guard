from x_impersonation_guard.utils.image_hash import (
    hamming_distance,
    similarity_from_hashes,
)


def test_hamming_distance_for_hex_hashes() -> None:
    assert hamming_distance("0000000000000000", "000000000000000f") == 4


def test_similarity_handles_missing_hashes() -> None:
    assert similarity_from_hashes(None, "0000000000000000") == 0.0


def test_similarity_converts_distance_to_score() -> None:
    assert similarity_from_hashes("0000000000000000", "000000000000000f") == 0.9375
