"""Every accepted setting must actually be persisted.

`_ws_update_settings` accepts keys via `_UPDATE_SETTINGS_SCHEMA` but only
*stores* the ones listed in `_TOP_LEVEL_SETTINGS` / `_SUBKEY_SETTINGS` (or
handled explicitly). A key added to the schema alone is accepted, reported as
a success to the caller, and then silently thrown away — which is exactly what
happened while building chore roulette (#677): the panel toggle appeared to
save, and nothing changed.
"""
from __future__ import annotations

import pathlib
import re

SRC = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components" / "taskmate" / "websocket.py"
).read_text(encoding="utf-8")

# Keys the handler deals with by hand rather than through the two sets.
_EXPLICIT = {"type", "time_periods", "vacation_periods", "parent_user_ids"}


def _string_set(name: str) -> set[str]:
    block = re.search(rf"^{name} = \{{(.*?)^\}}", SRC, re.S | re.M)
    assert block, f"could not find {name} in websocket.py"
    return set(re.findall(r'"([a-z_]+)"', block.group(1)))


def _schema_keys() -> set[str]:
    block = re.search(r"_UPDATE_SETTINGS_SCHEMA = \{(.*?)\n\}", SRC, re.S)
    assert block, "could not find _UPDATE_SETTINGS_SCHEMA"
    return set(re.findall(r'vol\.Optional\("([a-z_]+)"\)', block.group(1)))


def test_every_accepted_setting_is_persisted():
    """A schema key with nowhere to be stored is a silent data-loss bug."""
    accepted = _schema_keys()
    persisted = _string_set("_TOP_LEVEL_SETTINGS") | _string_set("_SUBKEY_SETTINGS") | _EXPLICIT
    orphans = sorted(accepted - persisted)
    assert orphans == [], (
        f"accepted by the schema but never stored: {orphans}. "
        "Add them to _SUBKEY_SETTINGS (or handle them explicitly)."
    )


def test_no_persisted_setting_is_unreachable():
    """A storable key the schema rejects can never be set by the panel."""
    accepted = _schema_keys()
    subkeys = _string_set("_SUBKEY_SETTINGS")
    unreachable = sorted(subkeys - accepted)
    assert unreachable == [], (
        f"storable but not accepted by the schema: {unreachable}"
    )


def test_roulette_settings_round_trip():
    """The specific regression that motivated this file."""
    accepted = _schema_keys()
    subkeys = _string_set("_SUBKEY_SETTINGS")
    for key in ("roulette_enabled", "roulette_multiplier", "roulette_daily_spins"):
        assert key in accepted, f"{key} missing from _UPDATE_SETTINGS_SCHEMA"
        assert key in subkeys, f"{key} missing from _SUBKEY_SETTINGS"
