"""Image hash helpers."""

from __future__ import annotations

from pathlib import Path

import imagehash
from PIL import Image


def phash_image(path: Path) -> str:
    with Image.open(path) as image:
        return str(imagehash.phash(image))


def hamming_distance(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    if len(left) != len(right):
        raise ValueError("hashes must have equal length")
    left_int = int(left, 16)
    right_int = int(right, 16)
    return (left_int ^ right_int).bit_count()


def similarity_from_hashes(left: str | None, right: str | None) -> float:
    distance = hamming_distance(left, right)
    if distance is None:
        return 0.0
    return max(0.0, 1.0 - (distance / 64.0))
