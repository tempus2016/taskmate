"""Whole-app hardening, October 2026: a restored backup is content, not a
grant of access; a photo is one submission's evidence; the kiosk PIN limiter
is per caller; the calendar entity fails closed; the audit log keeps its
history; shared template packs are normalised."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate as tm
from custom_components.taskmate import kiosk, photos
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion
from custom_components.taskmate.storage import TaskMateStorage
from tests.conftest import FakeStore

UTC = dt.timezone.utc


def run(coro):
    return asyncio.run(coro)


async def _storage() -> TaskMateStorage:
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "hardening"
    storage._store = FakeStore(None, 1, "hardening")
    storage._data = {}
    await storage.async_load()
    return storage


# ── backup export leaves secrets behind ─────────────────────────────────────


def test_export_omits_pin_hashes_calendar_token_and_running_unlocks():
    async def go():
        s = await _storage()
        s.add_child(Child(name="Mia", id="c1"))
        s.set_kiosk_pin_hash("c1", "pbkdf2_sha256$1$00$00")
        s.set_setting("ics_token", "feed-token")
        s.set_setting("active_unlocks", [{"entity_id": "switch.tv"}])
        snap = s.export_data()
        assert "kiosk_pins" not in snap
        assert "ics_token" not in snap["settings"]
        assert "active_unlocks" not in snap["settings"]
        assert "pbkdf2" not in json.dumps(snap) and "feed-token" not in json.dumps(snap)
        # The live store still has them.
        assert s.get_kiosk_pin_hash("c1") and s.get_setting("ics_token") == "feed-token"

    run(go())


# ── backup import keeps this instance's authorisation state ─────────────────


def _crafted():
    return {
        "children": [
            {"id": "c1", "name": "Mia", "linked_user_id": "uid-attacker"},
            {"id": "c2", "name": "New kid", "linked_user_id": "uid-attacker"},
        ],
        "settings": {
            "parent_user_ids": ["uid-attacker"],
            "require_linked_child": False,
            "unlock_allowlist": ["cover", "lock"],
            "ics_token": "known-token",
            "active_unlocks": [
                {"entity_id": ["alarm_control_panel.house", "lock.front"], "revert_at": "2000-01-01T00:00:00+00:00"}
            ],
            "notification_nav_url": "intent://evil#Intent;end",
        },
        "kiosk_pins": {"c1": "pbkdf2_sha256$1$00$00"},
        "audit_log": [{"id": "forged", "action": "nothing happened"}],
        "notification_config": {"chore_completed": {"nav_url": "app://x", "group": "ok group"}},
        "points_name": "<img src=x onerror=alert(1)>",
        "points_icon": 5,
    }


def test_import_keeps_parents_links_pins_allowlist_and_audit_from_this_instance():
    async def go():
        s = await _storage()
        s.add_child(Child(name="Mia", id="c1", linked_user_id="uid-mia"))
        s.set_parent_user_ids(["uid-parent"])
        s.set_setting("require_linked_child", True)
        s.set_setting("unlock_allowlist", ["switch"])
        s.set_kiosk_pin_hash("c1", "pbkdf2_sha256$1$aa$aa")
        s.set_setting("ics_token", "mine")
        s.add_audit_entry({"id": "real", "ts": "2026-10-01T00:00:00+00:00", "action": "x"})

        s.import_data(_crafted())

        assert s.get_parent_user_ids() == ["uid-parent"]
        assert s.get_require_linked_child() is True
        assert s.get_setting("unlock_allowlist") == ["switch"]
        assert s.get_kiosk_pin_hash("c1") == "pbkdf2_sha256$1$aa$aa"
        links = {c.id: c.linked_user_id for c in s.get_children()}
        # The known child keeps its own link; a child new to this instance has none.
        assert links == {"c1": "uid-mia", "c2": ""}
        assert s.get_setting("ics_token", "") == ""
        assert s.get_setting("active_unlocks", []) == []
        assert [e["id"] for e in s._data["audit_log"]] == ["real"]

    run(go())


def test_import_on_a_fresh_instance_grants_nobody_anything():
    async def go():
        s = await _storage()
        s.import_data(_crafted())
        assert s.get_parent_user_ids() == []
        assert s.get_kiosk_pin_child_ids() == []
        assert all(c.linked_user_id == "" for c in s.get_children())
        assert s.get_setting("unlock_allowlist", None) is None

    run(go())


def test_import_bounds_the_points_name_and_icon():
    async def go():
        s = await _storage()
        s.import_data(_crafted())
        # Whatever it is, it is a bounded string the panel escapes; a crafted
        # value is kept as text (the panel escapes it) but never a non-string.
        assert isinstance(s.get_points_name(), str) and len(s.get_points_name()) <= 120
        assert s._data["points_icon"] == "mdi:star"
        s.import_data({"points_name": 5})
        assert s.get_points_name() == "Stars"
        s.import_data({"points_name": "x" * 500})
        assert len(s.get_points_name()) == 120

    run(go())


def test_import_vets_notification_tap_targets():
    async def go():
        s = await _storage()
        s.import_data(_crafted())
        assert "notification_nav_url" not in s._data["settings"]
        cfg = s._data["notification_config"]["chore_completed"]
        assert cfg["nav_url"] == "" and cfg["group"] == ""
        s.import_data({"settings": {"notification_nav_url": "/lovelace/kids"}})
        assert s._data["settings"]["notification_nav_url"] == "/lovelace/kids"

    run(go())


def test_import_drops_a_record_that_cannot_load_instead_of_crashing_every_read():
    async def go():
        s = await _storage()
        s.import_data(
            {
                "chores": [
                    {"id": "ok", "name": "Bin", "points": 5},
                    {"id": "bad", "name": "Boom", "weekly_target": "x"},
                    {"id": "bad2", "name": "Boom", "assigned_to": 7},
                ],
                "children": [{"id": "k", "name": "Kid", "level": "high"}],
            }
        )
        assert [c.id for c in s.get_chores()] == ["ok"]
        assert s.get_children() == []

    run(go())


def test_round_trip_through_export_and_import_keeps_content():
    async def go():
        s = await _storage()
        s.add_child(Child(name="Mia", id="c1", linked_user_id="uid-mia"))
        s.add_chore(Chore(name="Bin", points=5, id="ch1"))
        s.set_parent_user_ids(["uid-parent"])
        snap = s.export_data()
        s.import_data(snap)
        assert [c.id for c in s.get_chores()] == ["ch1"]
        assert s.get_children()[0].linked_user_id == "uid-mia"
        assert s.get_parent_user_ids() == ["uid-parent"]

    run(go())


# ── a stored unlock record must be one plain entity id ──────────────────────


def test_unlock_resume_ignores_a_record_whose_entity_is_not_a_single_id():
    from tests.test_timed_unlocks import _coord

    past = "2000-01-01T00:00:00+00:00"
    coord = _coord(
        ["switch"], [{"entity_id": ["switch.a", "lock.b"], "revert_at": past}, {"entity_id": "all", "revert_at": past}]
    )
    assert run(coord.async_resume_unlocks()) == 2
    coord.hass.services.async_call.assert_not_awaited()
    assert coord.active_unlocks() == []


# ── a photo is one submission's evidence ────────────────────────────────────


def _photo(letter):
    return "/api/taskmate/photo/" + letter * 32 + ".jpg"


def test_a_photo_already_attached_to_another_completion_is_refused():
    from tests.test_photo_proof import _coord

    chore = Chore(name="Room", requires_approval=True, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    siblings = ChoreCompletion(chore_id="ch1", child_id="c2", completed_at=dt.datetime.now(UTC), photo_url=_photo("a"))
    coord.storage.get_completions = MagicMock(return_value=[siblings])
    coord.storage._data = {}
    with pytest.raises(Exception, match="photo"):
        run(coord.async_complete_chore("ch1", "c1", photo_url=_photo("a")))
    assert coord._added == []


def test_a_photo_held_by_a_half_formed_team_counts_as_in_use():
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=[])
    storage._data = {
        "team_joins": {"ch": {"date": "2026-10-16", "joined": [{"child_id": "c1", "photo_url": _photo("b")}]}}
    }
    assert photos.is_photo_in_use(storage, _photo("b")) is True
    assert photos.is_photo_in_use(storage, _photo("c")) is False
    assert _photo("b") in photos.referenced_photo_urls(storage)


def test_reversal_does_not_delete_a_file_another_record_still_uses():
    deleted = []

    async def _delete(hass, url):
        deleted.append(url)

    storage = MagicMock()
    storage._data = {}
    other = ChoreCompletion(chore_id="ch1", child_id="c2", completed_at=dt.datetime.now(UTC), photo_url=_photo("a"))
    storage.get_completions = MagicMock(return_value=[other])
    orig = photos.async_delete_photo
    photos.async_delete_photo = _delete
    try:
        assert run(photos.async_delete_photo_if_unreferenced(MagicMock(), storage, _photo("a"))) is False
        assert run(photos.async_delete_photo_if_unreferenced(MagicMock(), storage, _photo("z"))) is True
    finally:
        photos.async_delete_photo = orig
    assert deleted == [_photo("z")]


def test_upload_view_bounds_the_body_read_and_sweeps_when_full():
    src = (pathlib.Path(__file__).resolve().parent.parent / "custom_components/taskmate/http_photos.py").read_text()
    assert "asyncio.timeout(self.BODY_READ_SECONDS)" in src
    assert "HTTPStatus.REQUEST_TIMEOUT" in src
    assert "_async_sweep_when_full" in src and "FULL_BUDGET_SWEEP_HOURS" in src


# ── kiosk PIN limiter: per caller, and the escalation forgets ────────────────


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_another_account_cannot_lock_a_childs_pad():
    limiter = kiosk.PinRateLimiter(_Clock())
    elsewhere = kiosk.limiter_key("malia", "uid-sibling-phone")
    tablet = kiosk.limiter_key("malia", "uid-tablet")
    for _ in range(kiosk.MAX_FAILURES):
        limiter.begin_attempt(elsewhere)
    assert limiter.locked_for(elsewhere) > 0
    assert limiter.locked_for(tablet) == 0
    assert limiter.begin_attempt(tablet) == 0


def test_lockout_escalation_decays_after_a_quiet_hour():
    clock = _Clock()
    limiter = kiosk.PinRateLimiter(clock)
    key = kiosk.limiter_key("malia", "uid-tablet")
    for _ in range(2):
        for _ in range(kiosk.MAX_FAILURES):
            limiter.begin_attempt(key)
        clock.now += limiter.locked_for(key)
    # Two lockouts so far: the next would be 120 s.
    clock.now += kiosk.LOCKOUT_DECAY_SECONDS + 1
    for _ in range(kiosk.MAX_FAILURES):
        limiter.begin_attempt(key)
    assert limiter.locked_for(key) == kiosk.BASE_LOCK_SECONDS


def test_a_new_pin_clears_every_callers_record():
    limiter = kiosk.PinRateLimiter(_Clock())
    for user in ("a", "b"):
        for _ in range(kiosk.MAX_FAILURES):
            limiter.begin_attempt(kiosk.limiter_key("malia", user))
    limiter.reset_child("malia")
    assert limiter.locked_for(kiosk.limiter_key("malia", "a")) == 0
    assert limiter.locked_for(kiosk.limiter_key("malia", "b")) == 0


async def test_verify_pin_limits_are_keyed_on_the_connection_user(hass):
    from tests.test_kiosk import _connection, _result
    from tests.test_kiosk import _storage as _kiosk_storage

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.storage = await _kiosk_storage(hass)
    coord.storage.add_child(Child(name="Malia", id="malia"))
    coord.storage.set_kiosk_pin_hash("malia", kiosk.hash_pin("1234", iterations=1000))
    hass.data = {tm.DOMAIN: {"k": coord}}

    async def _executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = _executor

    async def verify(user, pin):
        conn = _connection(user)
        await kiosk.ws_kiosk_verify_pin(
            hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_VERIFY_PIN, "child_id": "malia", "pin": pin}
        )
        return _result(conn)

    for _ in range(kiosk.MAX_FAILURES):
        await verify("uid-elsewhere", "0000")
    assert (await verify("uid-elsewhere", "1234"))["ok"] is False
    assert (await verify("uid-tablet", "1234"))["ok"] is True


def test_non_admin_handlers_do_not_echo_exception_text():
    root = pathlib.Path(__file__).resolve().parent.parent / "custom_components/taskmate"
    for name in ("kiosk.py", "websocket_auctions.py", "websocket_recaps.py"):
        src = (root / name).read_text()
        assert '"handler_failed", str(err)' not in src, name


# ── calendar entity: no identifiable caller is a refusal, not a pass ────────


async def test_calendar_edit_with_neither_connection_nor_context_is_refused(hass):
    from tests.test_calendar_two_way import _cal, _coord, current_connection

    cal = _cal(await _coord(hass))
    current_connection.set(None)
    cal._edit_context = None
    with pytest.raises(tm.Unauthorized):
        await cal._async_require_parent()


async def test_calendar_edit_from_a_userless_context_is_still_trusted(hass):
    from types import SimpleNamespace

    from tests.test_calendar_two_way import _cal, _coord, current_connection

    cal = _cal(await _coord(hass))
    current_connection.set(None)
    cal.async_set_context(SimpleNamespace(user_id=None))
    assert await cal._async_require_parent() == ""


def test_calendar_cleanup_never_deletes_a_repeating_event_by_name_alone():
    src = (pathlib.Path(__file__).resolve().parent.parent / "custom_components/taskmate/coord_calendar.py").read_text()
    assert 'if event.get("rrule") or event.get("recurrence_id"):' in src
    assert 'payload["recurrence_id"] = event["recurrence_id"]' in src


# ── audit log: denied attempts are recorded, bursts are folded ──────────────


def test_repeated_identical_entries_fold_into_one_line():
    async def go():
        s = await _storage()
        for i in range(600):
            s.add_audit_entry(
                {
                    "id": str(i),
                    "ts": f"2026-10-16T10:{i // 60:02d}:{i % 60:02d}+00:00",
                    "user_id": "kid",
                    "action": "service.choose_avatar",
                    "target": "Mia",
                }
            )
        log = s._data["audit_log"]
        assert len(log) < 20
        assert sum(int(e.get("count", 1)) for e in log) == 600
        assert s.get_audit_dropped_count() == 0
        # A different actor or action starts a fresh line.
        s.add_audit_entry(
            {
                "id": "p",
                "ts": "2026-10-16T10:09:59+00:00",
                "user_id": "parent",
                "action": "service.approve_chore",
                "target": "Mia",
            }
        )
        assert log[-1]["action"] == "service.approve_chore" and "count" not in log[-1]

    run(go())


@pytest.mark.asyncio
async def test_denied_service_calls_are_audited():
    coord = object.__new__(TaskMateCoordinator)
    coord.async_record_audit = AsyncMock()
    coord.get_child = MagicMock(return_value=None)
    coord.storage = MagicMock()
    coord.storage.get_parent_user_ids = MagicMock(return_value=[])
    hass = MagicMock()
    hass.data = {tm.DOMAIN: {"entry": coord}}
    hass.auth.async_get_user = AsyncMock(return_value=MagicMock(is_admin=False, name="Kid"))
    hass.services.async_register = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    await tm._async_register_services(hass)
    registered = {c.args[1]: c.args[2] for c in hass.services.async_register.call_args_list}
    call = MagicMock()
    call.context.user_id = "uid-kid"
    call.service = "gift_points"
    call.data = {"child_id": "c1", "points": 5}
    with pytest.raises(tm.Unauthorized):
        await registered["gift_points"](call)
    args = coord.async_record_audit.await_args.args
    assert args[0] == "uid-kid" and args[2] == "service.gift_points (denied)"


# ── shared template packs: unknown option words fall back ───────────────────


@pytest.mark.asyncio
async def test_pack_import_normalises_enum_fields():
    from tests.test_template_packs import _coord, _pack

    coord = _coord()
    await coord.async_import_pack(
        _pack(
            templates=[
                {
                    "name": "Odd",
                    "chores": [
                        {
                            "name": "Bed",
                            "time_category": "<b>x</b>",
                            "visibility_operator": "spooky",
                            "first_occurrence_mode": "never",
                            "task_type": "quantum",
                        }
                    ],
                }
            ]
        )
    )
    chore = coord._store[-1]["chores"][0]
    assert chore["time_category"] == "anytime"
    assert chore["visibility_operator"] == "equals"
    assert chore["first_occurrence_mode"] == "available_immediately"
    assert chore["task_type"] == "standard"


# ── parent-edited templates: an attribute placeholder can't raise ───────────


def test_read_aloud_template_with_attribute_placeholder_falls_back():
    from custom_components.taskmate.coord_tts import DEFAULT_TEMPLATE
    from tests.test_read_aloud import _chore, _coord

    coord = _coord([_chore("a"), _chore("b")], {"read_aloud_template": "{name.__class__}"})
    assert coord.build_read_aloud_message("kid1") == DEFAULT_TEMPLATE.format(name="Ella", count=2, chores="a and b")
