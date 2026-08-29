"""Guard the weekday abbreviations against context-free machine translation.

Issue #833: the German weekly card rendered "Heiraten" for Wed and "Sonne" for
Sun — the English three-letter abbreviations had been translated as the verb
"to wed" and the noun "sun". The Translation parity check only asserts a key
exists, so a plausible-looking wrong word passes it.

Every locale carries the same seven abbreviations three times over
(``weekly.day_*`` on the weekly card, ``panel.day_*`` in the chore editor,
``panel.notif_day_*`` in the notification schedule). They must agree: any locale
where one block disagrees with the others has had that block translated in
isolation, which is exactly how #833 happened.
"""

import glob
import json
import os

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
PREFIXES = ("weekly.day_", "panel.day_", "panel.notif_day_")


def _locale_files() -> list[str]:
    base = os.path.join(
        os.path.dirname(__file__),
        "..",
        "custom_components",
        "taskmate",
        "www",
        "locales",
    )
    files = glob.glob(os.path.join(base, "*.json"))
    assert files, "no locale files found"
    return files


def test_weekday_abbreviations_agree_across_blocks():
    for path in _locale_files():
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for day in DAYS:
            values = {prefix: data.get(f"{prefix}{day}") for prefix in PREFIXES}
            assert len(set(values.values())) == 1, (
                f"{name}: weekday '{day}' differs between blocks — {values}. "
                "One of these was translated without the others; they are the "
                "same abbreviation and must match."
            )


def test_weekday_abbreviations_are_short():
    """An abbreviation is 1-4 characters. A whole word means a bad translation.

    "Heiraten" (8) and "Sonne" (5) both fail this; every legitimate
    abbreviation currently shipped is 2-3 characters.
    """
    for path in _locale_files():
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for prefix in PREFIXES:
            for day in DAYS:
                key = f"{prefix}{day}"
                value = data.get(key)
                assert value, f"{name}: {key} missing/empty"
                assert len(value) <= 4, f"{name}: {key} is {value!r} — that is a word, not a weekday abbreviation."
