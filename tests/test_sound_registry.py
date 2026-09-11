"""Registry + cascade behaviour for custom completion sounds (#856).

Covers the storage layer and the SoundsMixin coordinator methods behind the
``taskmate/add_custom_sound`` / ``rename`` / ``remove`` websocket commands.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.taskmate import sounds
from custom_components.taskmate.coord_sounds import SoundsMixin
from custom_components.taskmate.models import CustomSound
from custom_components.taskmate.storage import TaskMateStorage

NAME = "a" * 32 + ".mp3"
OTHER = "b" * 32 + ".ogg"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_storage(initial_data: dict | None = None) -> TaskMateStorage:
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = initial_data if initial_data is not None else {}
    storage._data_version = 0
    storage.hass = MagicMock()
    return storage


class _Coordinator(SoundsMixin):
    """Minimal host for the mixin: storage + hass + the two async hooks."""

    def __init__(self, storage, tmp_path: Path):
        self.storage = storage
        self.refreshed = 0
        hass = MagicMock()
        hass.config.path = MagicMock(side_effect=lambda *p: str(Path(tmp_path, *p)))

        async def _exec(func, *args):
            return func(*args)

        hass.async_add_executor_job = _exec
        self.hass = hass

    async def async_refresh(self):
        self.refreshed += 1


def _coord(tmp_path, data=None):
    storage = _make_storage(data if data is not None else {})
    storage.async_save = _noop_save(storage)
    return _Coordinator(storage, tmp_path)


def _noop_save(storage):
    async def _save():
        storage._data_version += 1

    return _save


# ---------------------------------------------------------------------------
# Storage layer
# ---------------------------------------------------------------------------


def test_add_and_get_custom_sound():
    storage = _make_storage({})
    storage.add_custom_sound(CustomSound(name="Burp", file=NAME))
    got = storage.get_custom_sound(NAME)
    assert got is not None
    assert got.name == "Burp"
    assert [s.file for s in storage.get_custom_sounds()] == [NAME]


def test_get_custom_sound_returns_none_when_absent():
    assert _make_storage({}).get_custom_sound(NAME) is None


def test_rename_custom_sound():
    storage = _make_storage({})
    storage.add_custom_sound(CustomSound(name="Old", file=NAME))
    assert storage.rename_custom_sound(NAME, "New") is True
    assert storage.get_custom_sound(NAME).name == "New"


def test_rename_custom_sound_reports_unknown():
    assert _make_storage({}).rename_custom_sound(NAME, "New") is False


def test_remove_custom_sound():
    storage = _make_storage({})
    storage.add_custom_sound(CustomSound(name="Burp", file=NAME))
    storage.add_custom_sound(CustomSound(name="Other", file=OTHER))
    storage.remove_custom_sound(NAME)
    assert [s.file for s in storage.get_custom_sounds()] == [OTHER]


def test_reset_chores_using_sound_rewrites_only_matches():
    storage = _make_storage(
        {
            "chores": [
                {"id": "1", "completion_sound": f"custom:{NAME}"},
                {"id": "2", "completion_sound": f"custom:{OTHER}"},
                {"id": "3", "completion_sound": "levelup"},
                {"id": "4", "completion_sound": f"custom:{NAME}"},
            ]
        }
    )
    assert storage.reset_chores_using_sound(f"custom:{NAME}") == 2
    by_id = {c["id"]: c["completion_sound"] for c in storage._data["chores"]}
    assert by_id == {
        "1": "coin",
        "2": f"custom:{OTHER}",
        "3": "levelup",
        "4": "coin",
    }


def test_custom_sounds_survive_a_load_on_an_existing_install():
    # Installs that predate #856 have no custom_sounds key; load must add it
    # rather than leaving get_custom_sounds() to trip over a missing list.
    storage = _make_storage({"children": [], "chores": []})
    storage.hass = MagicMock()
    assert storage.get_custom_sounds() == []


# ---------------------------------------------------------------------------
# Coordinator mixin
# ---------------------------------------------------------------------------


def test_async_add_custom_sound_registers_and_refreshes(tmp_path):
    coord = _coord(tmp_path)
    sound = run(coord.async_add_custom_sound(NAME, "  Burp  Noise  "))
    assert sound.file == NAME
    # The display name is normalised on the way in.
    assert sound.name == "Burp Noise"
    assert coord.storage.get_custom_sound(NAME).name == "Burp Noise"
    assert coord.refreshed == 1


def test_async_add_custom_sound_rejects_a_bad_filename(tmp_path):
    coord = _coord(tmp_path)
    for bad in ("../../secrets.yaml", "", "nope.mp3", "a" * 32 + ".exe"):
        try:
            run(coord.async_add_custom_sound(bad, "X"))
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_async_add_custom_sound_rejects_a_duplicate(tmp_path):
    coord = _coord(tmp_path)
    run(coord.async_add_custom_sound(NAME, "First"))
    try:
        run(coord.async_add_custom_sound(NAME, "Second"))
    except ValueError:
        return
    raise AssertionError("accepted a duplicate registration")


def test_async_rename_custom_sound(tmp_path):
    coord = _coord(tmp_path)
    run(coord.async_add_custom_sound(NAME, "Old"))
    sound = run(coord.async_rename_custom_sound(NAME, "New"))
    assert sound.name == "New"


def test_async_rename_custom_sound_rejects_unknown(tmp_path):
    coord = _coord(tmp_path)
    try:
        run(coord.async_rename_custom_sound(NAME, "New"))
    except ValueError:
        return
    raise AssertionError("renamed a sound that was never registered")


def test_async_remove_custom_sound_deletes_file_and_resets_chores(tmp_path):
    coord = _coord(tmp_path)
    directory = sounds.sounds_path(coord.hass)
    directory.mkdir(parents=True)
    (directory / NAME).write_bytes(b"ID3\x03\x00")

    run(coord.async_add_custom_sound(NAME, "Burp"))
    coord.storage._data["chores"] = [
        {"id": "1", "completion_sound": f"custom:{NAME}"},
        {"id": "2", "completion_sound": "coin"},
    ]

    reset = run(coord.async_remove_custom_sound(NAME))

    assert reset == 1
    assert coord.storage.get_custom_sound(NAME) is None
    assert not (directory / NAME).exists()
    # A chore left pointing at a deleted sound would silently play nothing.
    assert coord.storage._data["chores"][0]["completion_sound"] == "coin"


def test_async_remove_custom_sound_rejects_unknown(tmp_path):
    coord = _coord(tmp_path)
    try:
        run(coord.async_remove_custom_sound(NAME))
    except ValueError:
        return
    raise AssertionError("removed a sound that was never registered")


def test_custom_sounds_state_shape(tmp_path, monkeypatch):
    coord = _coord(tmp_path)
    run(coord.async_add_custom_sound(NAME, "Burp"))
    # Pin the signer: under the real HA harness async_sign_path imports and runs
    # for real, reaching into hass.data on our MagicMock. The URL signing itself
    # is HA's business; what this test owns is the row shape.
    monkeypatch.setattr("custom_components.taskmate.coord_sounds.sign_sound_url", lambda hass, url: url)
    state = coord.custom_sounds_state()
    assert len(state) == 1
    row = state[0]
    # value is what a chore stores; url is what the card plays.
    assert row["value"] == f"custom:{NAME}"
    assert row["file"] == NAME
    assert row["name"] == "Burp"
    assert row["url"].startswith("/api/taskmate/sound/")


def test_custom_sounds_state_is_empty_by_default(tmp_path):
    assert _coord(tmp_path).custom_sounds_state() == []
