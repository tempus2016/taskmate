"""NFC / QR tag completion (#923).

Scanning an HA tag linked to a chore completes it for the scanning child, via
the normal ``async_complete_chore`` path so every existing rule still applies.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import EVENT_TAG_COMPLETION, MAX_CHORE_TAGS, TAG_SCAN_DEBOUNCE_SECONDS
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore, normalize_tag_ids
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
NOW = dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)  # a Wednesday
TAG = "dishwasher-tag"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_system(users=None):
    """Real coordinator + storage over the conftest fakes.

    ``users`` maps HA user id -> is_admin for the authz lookups.
    """
    from tests.conftest import FakeHass, FakeStore

    users = users or {}
    hass = FakeHass()
    hass.states = SimpleNamespace(get=lambda entity_id: None)

    async def _get_user(user_id):
        if user_id not in users:
            return None
        return SimpleNamespace(id=user_id, name=f"user-{user_id}", is_admin=users[user_id])

    hass.auth = SimpleNamespace(async_get_user=_get_user)

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    return coord, storage


def _ctx(user_id):
    return SimpleNamespace(user_id=user_id)


def _setup(coord, *, assigned="alice", tags=(TAG,), **chore_kw):
    """Alice (linked to user 'u-alice') and Bob (linked to 'u-bob') + one tagged chore."""
    alice = run(coord.async_add_child("Alice", linked_user_id="u-alice"))
    bob = run(coord.async_add_child("Bob", linked_user_id="u-bob"))
    ids = {"alice": [alice.id], "bob": [bob.id], "both": [alice.id, bob.id], "none": []}[assigned]
    chore = run(
        coord.async_add_chore(
            "Empty the dishwasher",
            points=chore_kw.pop("points", 10),
            requires_approval=chore_kw.pop("requires_approval", False),
            daily_limit=chore_kw.pop("daily_limit", 1),
            assigned_to=ids,
        )
    )
    chore.tag_ids = list(tags)
    for k, v in chore_kw.items():
        setattr(chore, k, v)
    coord.storage.update_chore(chore)
    return alice, bob, chore


def _tag_events(coord):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == EVENT_TAG_COMPLETION]


@pytest.fixture(autouse=True)
def _frozen_now():
    import custom_components.taskmate.coordinator as _mod

    with patch.object(_mod.dt_util, "now", return_value=NOW):
        yield


# ── model / schema ───────────────────────────────────────────────────────────


class TestTagIdsField:
    def test_old_data_defaults_to_no_tags(self):
        assert Chore.from_dict({"name": "Old chore"}).tag_ids == []

    def test_round_trip(self):
        chore = Chore.from_dict({"name": "x", "tag_ids": ["a", "b"]})
        assert Chore.from_dict(chore.to_dict()).tag_ids == ["a", "b"]

    def test_normalize_strips_dedupes_and_caps(self):
        assert normalize_tag_ids([" a ", "", "a", "b", None]) == ["a", "b"]
        assert normalize_tag_ids("not-a-list") == []
        assert len(normalize_tag_ids([f"t{i}" for i in range(50)])) == MAX_CHORE_TAGS

    def test_ws_schema_accepts_and_cleans(self):
        schema = vol.Schema(ws._chore_payload_schema(require_name=False))
        assert schema({"tag_ids": [" a ", "a", "b"]})["tag_ids"] == ["a", "b"]
        assert schema({"tag_ids": []})["tag_ids"] == []

    def test_ws_schema_rejects_bad_input(self):
        schema = vol.Schema(ws._chore_payload_schema(require_name=False))
        with pytest.raises(vol.Invalid):
            schema({"tag_ids": [f"t{i}" for i in range(MAX_CHORE_TAGS + 1)]})
        with pytest.raises(vol.Invalid):
            schema({"tag_ids": ["x" * 500]})
        with pytest.raises(vol.Invalid):
            schema({"tag_ids": "single-string"})

    def test_tag_ids_is_editable(self):
        assert "tag_ids" in ws._CHORE_EDITABLE_FIELDS


# ── child resolution ─────────────────────────────────────────────────────────


class TestChildResolution:
    def test_linked_user_completes_for_their_child(self):
        coord, storage = _make_system({"u-alice": False})
        alice, _bob, chore = _setup(coord, assigned="both")
        result = run(coord.async_handle_tag_scan(TAG, device_id="phone-1", context=_ctx("u-alice")))
        assert len(result) == 1
        assert result[0].child_id == alice.id
        assert storage.get_child(alice.id).points == 10
        events = _tag_events(coord)
        assert len(events) == 1
        assert events[0]["child_id"] == alice.id
        assert events[0]["chore_id"] == chore.id
        assert events[0]["tag_id"] == TAG
        assert events[0]["device_id"] == "phone-1"
        assert events[0]["pending_approval"] is False

    def test_linked_user_is_not_redirected_to_the_single_assignee(self):
        # Alice scans Bob's chore: she is resolved, so it is HER completion
        # attempt (refused — not assigned), never a silent credit to Bob.
        coord, storage = _make_system({"u-alice": False})
        _alice, bob, _chore = _setup(coord, assigned="bob")
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert storage.get_completions() == []
        assert storage.get_child(bob.id).points == 0

    def test_unlinked_user_credits_single_assignee(self):
        coord, storage = _make_system({"u-parent": True})
        alice, _bob, _chore = _setup(coord, assigned="alice")
        result = run(coord.async_handle_tag_scan(TAG, context=_ctx("u-parent")))
        assert [c.child_id for c in result] == [alice.id]

    def test_userless_scan_credits_single_assignee(self):
        coord, _storage = _make_system()
        alice, _bob, _chore = _setup(coord, assigned="alice")
        result = run(coord.async_handle_tag_scan(TAG, context=None))
        assert [c.child_id for c in result] == [alice.id]

    @pytest.mark.parametrize("assigned", ["both", "none"])
    def test_unresolved_with_ambiguous_assignees_is_ignored(self, assigned):
        coord, storage = _make_system({"u-parent": True})
        _setup(coord, assigned=assigned)
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-parent"))) == []
        assert storage.get_completions() == []
        assert _tag_events(coord) == []

    def test_strict_mode_blocks_unlinked_non_parent_fallback(self):
        coord, storage = _make_system({"u-guest": False})
        _setup(coord, assigned="alice")
        storage.get_require_linked_child = lambda: True
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-guest"))) == []
        assert storage.get_completions() == []

    def test_unknown_tag_does_nothing(self):
        coord, storage = _make_system({"u-alice": False})
        _setup(coord)
        assert run(coord.async_handle_tag_scan("some-other-tag", context=_ctx("u-alice"))) == []
        assert run(coord.async_handle_tag_scan("", context=_ctx("u-alice"))) == []
        assert storage.get_completions() == []


# ── existing rules still apply ───────────────────────────────────────────────


class TestNormalCompletionRules:
    def test_approval_required_chore_goes_pending(self):
        coord, storage = _make_system({"u-alice": False})
        alice, _bob, _chore = _setup(coord, requires_approval=True)
        result = run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))
        assert len(result) == 1 and result[0].approved is False
        assert storage.get_child(alice.id).points == 0
        assert _tag_events(coord)[0]["pending_approval"] is True
        coord._async_notify_pending_approval.assert_awaited()

    @pytest.mark.parametrize("flag", ["require_photo", "open_ended"])
    def test_photo_or_note_chores_cannot_be_tag_completed(self, flag):
        coord, storage = _make_system({"u-alice": False})
        _setup(coord, **{flag: True})
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert storage.get_completions() == []

    def test_timed_chore_is_skipped(self):
        coord, storage = _make_system({"u-alice": False})
        _setup(coord, task_type="timed")
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert storage.get_completions() == []

    def test_disabled_chore_is_not_completed(self):
        coord, storage = _make_system({"u-alice": False})
        _setup(coord, enabled=False)
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert storage.get_completions() == []

    def test_goes_through_async_complete_chore(self):
        coord, _storage = _make_system({"u-alice": False})
        alice, _bob, chore = _setup(coord)
        coord.async_complete_chore = AsyncMock(return_value=None)
        run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))
        coord.async_complete_chore.assert_awaited_once_with(chore.id, alice.id)

    def test_one_tag_can_serve_one_chore_per_child(self):
        # The same sticker on the cat bowl, one "feed the cat" per child.
        coord, storage = _make_system({"u-alice": False, "u-bob": False})
        alice, bob, _chore = _setup(coord, assigned="alice")
        bobs = run(coord.async_add_chore("Feed the cat (Bob)", requires_approval=False, assigned_to=[bob.id]))
        bobs.tag_ids = [TAG]
        storage.update_chore(bobs)
        assert [c.child_id for c in run(coord.async_handle_tag_scan(TAG, context=_ctx("u-bob")))] == [bob.id]
        assert [c.child_id for c in run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))] == [alice.id]


# ── duplicate scans ──────────────────────────────────────────────────────────


class TestDuplicateScans:
    def test_second_scan_same_occurrence_is_noop(self):
        coord, storage = _make_system({"u-alice": False})
        alice, _bob, _chore = _setup(coord)
        run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))
        assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert len(storage.get_completions()) == 1
        assert storage.get_child(alice.id).points == 10
        assert len(_tag_events(coord)) == 1

    def test_double_read_ignored_even_when_daily_limit_allows_more(self):
        import custom_components.taskmate.coordinator as _mod

        coord, storage = _make_system({"u-alice": False})
        _setup(coord, daily_limit=3)
        run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))
        later = NOW + dt.timedelta(seconds=5)
        with patch.object(_mod.dt_util, "now", return_value=later):
            assert run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice"))) == []
        assert len(storage.get_completions()) == 1

        # A deliberate second go after the window is a new occurrence.
        much_later = NOW + dt.timedelta(seconds=TAG_SCAN_DEBOUNCE_SECONDS + 1)
        with patch.object(_mod.dt_util, "now", return_value=much_later):
            assert len(run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))) == 1
        assert len(storage.get_completions()) == 2


# ── event wiring ─────────────────────────────────────────────────────────────


class TestEventWiring:
    def test_listener_schedules_the_handler(self):
        coord, _storage = _make_system()
        coord.async_handle_tag_scan = MagicMock(return_value="coro")
        coord.hass.async_create_task = MagicMock()
        event = SimpleNamespace(data={"tag_id": TAG, "device_id": "dev"}, context=_ctx("u-alice"))
        coord._tag_scanned(event)
        coord.async_handle_tag_scan.assert_called_once()
        args, kwargs = coord.async_handle_tag_scan.call_args
        assert args == (TAG,)
        assert kwargs["device_id"] == "dev"
        assert kwargs["context"].user_id == "u-alice"
        coord.hass.async_create_task.assert_called_once_with("coro")

    def test_shutdown_unsubscribes(self):
        coord, storage = _make_system()
        unsub = MagicMock()
        coord._unsub_tag_scanned = unsub
        coord.cancel_unlock_timers = MagicMock()
        coord.notifications = MagicMock()
        coord.disarm_mandatory_schedules = MagicMock()
        storage.async_save_now = AsyncMock()
        run(coord.async_shutdown())
        unsub.assert_called_once()
        assert coord._unsub_tag_scanned is None

    def test_completion_is_audited(self):
        coord, storage = _make_system({"u-alice": False})
        _setup(coord)
        run(coord.async_handle_tag_scan(TAG, context=_ctx("u-alice")))
        entries = [e for e in storage.get_audit_log() if e["action"] == "tag.complete_chore"]
        assert len(entries) == 1
        assert entries[0]["user_id"] == "u-alice"
        assert entries[0]["target"] == "Alice"


# ── panel editor ─────────────────────────────────────────────────────────────


class TestPanelEditor:
    """The editor has to seed, render and send tag_ids, or the field can't be set."""

    PANEL = (
        pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"
    ).read_text(encoding="utf-8")

    def test_save_payload_sends_tag_ids(self):
        start = self.PANEL.index("  async _doSaveChore() {")
        assert "tag_ids: d.tag_ids" in self.PANEL[start : self.PANEL.index("const payload = wasAdd", start)]

    def test_dialog_renders_the_tags_section_and_lists_the_registry(self):
        assert "this._renderChoreTags(d)" in self.PANEL
        assert 'type: "tag/list"' in self.PANEL
        assert 'data-act="toggle-tag"' in self.PANEL
        assert 'act === "add-tag"' in self.PANEL

    def test_panel_limit_matches_backend(self):
        assert f"const MAX_CHORE_TAGS = {MAX_CHORE_TAGS};" in self.PANEL
