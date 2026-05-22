"""Handle variant generation for candidate discovery."""

from __future__ import annotations

from itertools import product

CONFUSABLES: dict[str, tuple[str, ...]] = {
    "o": ("0", "о"),
    "0": ("o", "о"),
    "l": ("1", "i"),
    "i": ("1", "l"),
    "s": ("5", "с"),
    "5": ("s",),
    "a": ("а",),
    "e": ("е",),
    "p": ("р",),
    "c": ("с",),
    "x": ("х",),
    "w": ("vv",),
    "m": ("rn",),
}

APPENDS = (
    "_real",
    "_official",
    "1",
    "2",
    "_",
    ".",
    "s",
    "_inc",
    "_eth",
    "_btc",
    "_capital",
    "_invests",
    "crypto",
    "signals",
)
PREPENDS = ("real_", "the_", "official_", "mr_", "_")
KEYBOARD_ADJACENT: dict[str, str] = {
    "w": "q",
    "h": "g",
    "e": "w",
    "l": "k",
    "i": "u",
    "n": "b",
    "v": "c",
    "s": "a",
    "t": "r",
    "o": "i",
    "r": "e",
}


def generate_handle_variants(
    handle: str, extra_patterns: list[str] | None = None
) -> list[str]:
    clean = handle.removeprefix("@").lower().strip()
    variants: set[str] = set()

    for suffix in APPENDS:
        variants.add(f"{clean}{suffix}")
    for prefix in PREPENDS:
        variants.add(f"{prefix}{clean}")
    if len(clean) > 2:
        variants.add(clean[:-1])
    if len(clean) > 3:
        variants.add(clean[:-2])

    variants.update(_single_character_substitutions(clean))
    variants.update(_multi_character_substitutions(clean))
    variants.update(_keyboard_typos(clean))

    for pattern in extra_patterns or []:
        variants.update(_expand_simple_glob(pattern.lower(), clean))

    variants.discard(clean)
    return sorted(value for value in variants if _valid_candidate_handle(value))


def _single_character_substitutions(handle: str) -> set[str]:
    variants: set[str] = set()
    for index, character in enumerate(handle):
        for replacement in CONFUSABLES.get(character, ()):
            variants.add(f"{handle[:index]}{replacement}{handle[index + 1 :]}")
    return variants


def _multi_character_substitutions(handle: str) -> set[str]:
    variants: set[str] = set()
    replacements = (("rn", "m"), ("m", "rn"), ("vv", "w"), ("w", "vv"))
    for old, new in replacements:
        if old in handle:
            variants.add(handle.replace(old, new, 1))
    return variants


def _keyboard_typos(handle: str) -> set[str]:
    variants: set[str] = set()
    for index, character in enumerate(handle):
        replacement = KEYBOARD_ADJACENT.get(character)
        if replacement:
            variants.add(f"{handle[:index]}{replacement}{handle[index + 1 :]}")
    return variants


def _expand_simple_glob(pattern: str, handle: str) -> set[str]:
    if "*" not in pattern:
        return {pattern}
    replacements = (handle, "real", "official", "capital", "investor")
    expanded: set[str] = set()
    star_count = pattern.count("*")
    for combo in product(replacements, repeat=star_count):
        result = pattern
        for replacement in combo:
            result = result.replace("*", replacement, 1)
        expanded.add(result)
    return expanded


def _valid_candidate_handle(handle: str) -> bool:
    if not 1 <= len(handle) <= 15:
        return False
    return all(character.isalnum() or character == "_" for character in handle)
