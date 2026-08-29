"""No NEW locale entry may ship the raw English string (#837).

`scripts/check_translations.py` asserts every key in en.json exists in every
locale. It never looks at the value, so "add the key, paste the English"
satisfies it — which is how the entire activity card (its chips, its relative
timestamps and its whole Lovelace editor) and the panel's skip-rotation button,
confirm dialog and toasts shipped in English to German, French, Norwegian and
Portuguese users. It is the same blind spot that let "Heiraten" through as the
German for Wednesday (#833).

A blanket "no value may equal English" rule does not work: plenty of values are
identical by coincidence and correct — units (`min`, `pts`), loanwords
(`Jackpot`, `Avatar`, `Bonus`), and words French and Portuguese share with
English (`Description`, `Notifications`, `Total`, `Rotation`). Nor does "only
flag multi-word values": the chips that shipped untranslated were single words
(`Rewards`, `Chores`, `Adjustments`).

So this is a ratchet. `tests/data/locale_english_baseline.json` freezes the
coincidences that existed when the activity-card strings were translated. Any
entry NOT in that baseline fails, whatever its length. The baseline is an upper
bound and should only ever shrink: translating one of its entries is welcome,
and pruning the key from the file is optional tidying, not a requirement.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "custom_components" / "taskmate" / "www" / "locales"
BASELINE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "locale_english_baseline.json"

REFERENCE = "en.json"
# en-GB is a spelling variant of the reference, not a translation.
SKIP_FILES = {"en.json", "en-GB.json"}


def _load(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _locale_files() -> list[str]:
    files = sorted(p.name for p in LOCALES_DIR.glob("*.json") if p.name not in SKIP_FILES)
    assert files, "no translated locale files found"
    return files


def _english_copies() -> dict[str, list[str]]:
    """Every locale entry whose value is byte-identical to English.

    Values with no letters at all (bare placeholders, numbers, symbols) cannot
    meaningfully differ between languages and are ignored.
    """
    en = _load(LOCALES_DIR / REFERENCE)
    found: dict[str, list[str]] = {}
    for name in _locale_files():
        data = _load(LOCALES_DIR / name)
        hits = sorted(
            key
            for key, value in data.items()
            if key in en
            and isinstance(value, str)
            and any(ch.isalpha() for ch in value)
            and value == en[key]
        )
        if hits:
            found[name] = hits
    return found


def test_no_new_untranslated_english_strings():
    baseline = _load(BASELINE_PATH)
    current = _english_copies()
    new = sorted(
        f"{name}: {key}"
        for name, keys in current.items()
        for key in keys
        if key not in baseline.get(name, [])
    )
    assert new == [], (
        "these locale entries are the untranslated English string:\n  "
        + "\n  ".join(new)
        + "\n\nTranslate them in the same PR as the feature. If a value really is "
        "identical in that language (a unit, a loanword, a product name), add the "
        "key to tests/data/locale_english_baseline.json under that locale."
    )


def test_baseline_only_names_keys_that_exist():
    """Stop the baseline rotting into a list of dead keys."""
    en = _load(LOCALES_DIR / REFERENCE)
    baseline = _load(BASELINE_PATH)
    unknown = sorted(
        f"{name}: {key}"
        for name, keys in baseline.items()
        for key in keys
        if key not in en
    )
    assert unknown == [], f"baseline names keys that no longer exist in en.json: {unknown}"


def test_baseline_covers_only_real_locales():
    baseline = _load(BASELINE_PATH)
    unknown = sorted(set(baseline) - set(_locale_files()))
    assert unknown == [], f"baseline names locale files that do not exist: {unknown}"


def test_the_activity_card_and_skip_rotation_strings_are_translated():
    """The exact regression from #837, pinned so it cannot come back.

    Listed explicitly rather than derived, so the pin cannot be silenced by
    adding one of these keys to the baseline. `activity.reason_bonus`
    ("Bonus: {name}") is deliberately absent — "Bonus" really is the word in
    German and Norwegian.
    """
    keys = [
        "activity.just_now",
        "activity.minutes_ago",
        "activity.hours_ago",
        "activity.days_ago",
        "activity.feed_end",
        "activity.filter_all",
        "activity.filter_chores",
        "activity.filter_rewards",
        "activity.filter_adjustments",
        "activity.filter_aria_label",
        "activity.no_events_for_filter",
        "activity.try_different_filter",
        "activity.editor.accent_stripes",
        "activity.editor.accent_stripes_helper",
        "activity.editor.show_filter_chips",
        "activity.editor.show_filter_chips_helper",
        "activity.editor.show_relative_time",
        "activity.editor.show_relative_time_helper",
        "panel.btn_skip_chore",
        "panel.skip_chore_confirm",
        "panel.toast_skip_done",
        "panel.toast_skip_failed",
    ]
    en = _load(LOCALES_DIR / REFERENCE)
    missing = [k for k in keys if k not in en]
    assert missing == [], f"pinned keys no longer exist in en.json: {missing}"

    offenders = []
    for name in _locale_files():
        data = _load(LOCALES_DIR / name)
        for key in keys:
            if data.get(key) == en[key]:
                offenders.append(f"{name}: {key} = {en[key]!r}")
    assert offenders == [], (
        "activity card / skip-rotation strings are back to English:\n  " + "\n  ".join(offenders)
    )
