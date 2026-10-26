"""Whole-app hardening, 25 October 2026: event entities keep private text
off the state machine; filename checks are exact; the photo upload budget is
per user; a restored backup keeps this instance's routing and devices; a
child's routine can't push their denied attempts out of the audit log; every
service is gated, audited, rate-limited and unregistered; help requests stay
on the child's own chores; a child's avatar is an icon or a safe picture URL."""

from __future__ import annotations

import asyncio
import datetime as dt
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.taskmate as tm
from custom_components.taskmate import images, photos, sounds
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child
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


# ── 1. event entities: the bus carries the text, the state machine must not ──


def test_help_request_event_entity_carries_who_and_what_but_not_the_message():
    from custom_components.taskmate.const import NOTIF_TYPE_HELP_REQUESTED
    from custom_components.taskmate.coord_notifications import notification_event_name
    from tests.test_event_entities import _setup

    hass, _coord, _listeners, added = _setup([Child(name="Malia", id="k1")])
    hass.bus.fire(
        notification_event_name(NOTIF_TYPE_HELP_REQUESTED),
        {
            "child_id": "k1",
            "child_name": "Malia",
            "chore_id": "ch1",
            "chore_name": "Bins",
            "message": "I wet the bed again",
            "message_text": " — “I wet the bed again”",
            "request_id": "req-1",
            "timestamp": "t",
        },
    )
    entity = next(e for e in added if getattr(e, "child_id", "") == "k1")
    event_type, attrs = entity.fired
    assert event_type == "help_requested"
    assert attrs["child_id"] == "k1" and attrs["chore_name"] == "Bins"
    for private in ("message", "message_text", "request_id"):
        assert private not in attrs, private


def test_appeal_and_completion_text_fields_stay_off_the_event_entity():
    from tests.test_event_entities import _setup

    hass, _coord, _listeners, added = _setup([Child(name="Malia", id="k1")])
    entity = next(e for e in added if getattr(e, "child_id", "") == "k1")
    hass.bus.fire(
        "taskmate_appeal_submitted",
        {"child_id": "k1", "kind": "chore", "item_name": "Bins", "message": "dad was wrong", "timestamp": "t"},
    )
    assert entity.fired[1] == {"child_id": "k1", "kind": "chore", "item_name": "Bins"}
    hass.bus.fire(
        "taskmate_chore_rejected",
        {"child_id": "k1", "chore_name": "Bins", "reason": "not done properly", "note": "sorry", "timestamp": "t"},
    )
    assert entity.fired[1] == {"child_id": "k1", "chore_name": "Bins"}


# ── 2. filename checks are exact: no trailing newline, no control bytes ─────


_HEX = "a" * 32


@pytest.mark.parametrize("tail", ["\n", "\r", "\r\n", "\x00", "\x1f"])
def test_photo_helpers_reject_a_name_with_a_trailing_control_character(tail):
    hass = MagicMock()
    hass.config.path = lambda *p: "/cfg/" + "/".join(p)
    url = f"{photos.URL_PREFIX}/{_HEX}.jpg{tail}"
    assert photos.is_taskmate_photo_url(url) is False
    assert photos.photo_file_for_url(hass, url) is None
    assert photos.FILENAME_RE.fullmatch(f"{_HEX}.jpg{tail}") is None


@pytest.mark.parametrize("tail", ["\n", "\r", "\x00"])
def test_image_helpers_reject_a_name_with_a_trailing_control_character(tail):
    hass = MagicMock()
    hass.config.path = lambda *p: "/cfg/" + "/".join(p)
    url = f"{images.URL_PREFIX}/{_HEX}.jpg{tail}"
    assert images.is_taskmate_image_url(url) is False
    assert images.normalize_taskmate_image_url(url) is None
    assert images.image_file_for_url(hass, url) is None


def test_image_normaliser_does_not_launder_a_control_character_hidden_in_the_query():
    assert images.normalize_taskmate_image_url(f"{images.URL_PREFIX}/{_HEX}.jpg") == f"{images.URL_PREFIX}/{_HEX}.jpg"
    assert images.normalize_taskmate_image_url(f"{images.URL_PREFIX}/{_HEX}.jpg?authSig=x\n") is None
    assert images.normalize_taskmate_image_url(f"{images.URL_PREFIX}/{_HEX}.jpg#\r") is None


@pytest.mark.parametrize("tail", ["\n", "\r", "\x00"])
def test_sound_helpers_reject_a_name_with_a_trailing_control_character(tail):
    hass = MagicMock()
    hass.config.path = lambda *p: "/cfg/" + "/".join(p)
    assert sounds.is_custom_sound(f"custom:{_HEX}.mp3{tail}") is False
    assert sounds.sound_id_for_value(f"custom:{_HEX}.mp3{tail}") is None
    assert sounds.sound_file_for_name(hass, f"{_HEX}.mp3{tail}") is None


def test_the_well_formed_names_still_pass():
    assert photos.is_taskmate_photo_url(f"{photos.URL_PREFIX}/{_HEX}.jpg") is True
    assert images.is_taskmate_image_url(f"{images.URL_PREFIX}/{_HEX}.png") is True
    assert sounds.is_custom_sound(f"custom:{_HEX}.mp3") is True


# ── 3. the photo upload budget is per user ──────────────────────────────────
# aiohttp and the HA http component are not installed in the test
# environment; the view only needs ``web.Response`` and the two
# ``HomeAssistantView`` reply helpers, so stub exactly those (the way
# ``test_event_entities`` stubs ``EventEntity``) and drive ``post`` directly.


class _Response:
    def __init__(self, status=200, body=b"", **kwargs):
        self.status = status
        self.body = body


class _HomeAssistantView:
    def json_message(self, message, status_code=200, **kwargs):
        return _Response(status=int(status_code), body=message)

    def json(self, result, status_code=200, **kwargs):
        return _Response(status=int(status_code), body=result)


if "aiohttp" not in sys.modules:
    _aiohttp = types.ModuleType("aiohttp")
    _web = types.ModuleType("aiohttp.web")
    _web.Response = _Response
    _web.Request = object
    _aiohttp.web = _web
    sys.modules["aiohttp"] = _aiohttp
    sys.modules["aiohttp.web"] = _web
_http_stub = sys.modules.get("homeassistant.components.http") or MagicMock()
_http_stub.HomeAssistantView = _HomeAssistantView
sys.modules["homeassistant.components.http"] = _http_stub

from custom_components.taskmate import http_photos  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60


def _upload_env(tmp_path):
    hass = MagicMock()
    hass.config.path = lambda *p: str(tmp_path.joinpath(*p))

    async def _executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = _executor
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_completions = MagicMock(return_value=[])
    coord.storage.get_parent_user_ids = MagicMock(return_value=[])
    coord.storage._data = {}
    hass.data = {DOMAIN: {"entry": coord}}
    return hass, http_photos.TaskMatePhotoUploadView(hass)


def _request(user_id, body=JPEG):
    field = MagicMock()
    field.name = "file"
    chunks = [bytes(body), b""]
    field.read_chunk = AsyncMock(side_effect=lambda *a, **k: chunks.pop(0))
    reader = MagicMock()
    parts = [field, None]
    reader.next = AsyncMock(side_effect=lambda: parts.pop(0))
    request = MagicMock()
    request.get = lambda key, default=None: {"hass_user": SimpleNamespace(id=user_id, is_admin=False)}.get(key, default)
    request.content_length = len(body)
    request.multipart = AsyncMock(return_value=reader)
    return request


def test_one_users_unattached_uploads_do_not_spend_another_users_budget(tmp_path):
    async def go():
        _hass, view = _upload_env(tmp_path)
        view.PER_USER_UNATTACHED_BUDGET = len(JPEG) * 2
        first = await view.post(_request("uid-kid"))
        second = await view.post(_request("uid-kid"))
        assert (first.status, second.status) == (200, 200)
        third = await view.post(_request("uid-kid"))
        assert third.status == 413
        assert isinstance(third.body, str) and third.body and "{" not in third.body
        # A sibling (a different HA user) is unaffected by the first child's pile.
        other = await view.post(_request("uid-sibling"))
        assert other.status == 200
        assert len(list((tmp_path / photos.PHOTOS_DIR).iterdir())) == 3

    run(go())


def test_a_full_pool_sweeps_the_requesting_users_own_fresh_uploads_first(tmp_path, monkeypatch):
    async def go():
        _hass, view = _upload_env(tmp_path)
        first = await view.post(_request("uid-kid"))
        assert first.status == 200
        before = {p.name for p in (tmp_path / photos.PHOTOS_DIR).iterdir()}
        # The pool is now "full": nothing else fits until something goes.
        monkeypatch.setattr(photos, "MAX_TOTAL_BYTES", len(JPEG))
        # Another user's upload must not evict the first child's minute-old file.
        blocked = await view.post(_request("uid-sibling"))
        assert blocked.status == 507
        assert {p.name for p in (tmp_path / photos.PHOTOS_DIR).iterdir()} == before
        # The same child uploading again replaces their own unattached file.
        replaced = await view.post(_request("uid-kid"))
        assert replaced.status == 200
        after = {p.name for p in (tmp_path / photos.PHOTOS_DIR).iterdir()}
        assert len(after) == 1 and not (after & before)

    run(go())


def test_upload_is_refused_at_once_when_every_slot_is_busy(tmp_path):
    async def go():
        _hass, view = _upload_env(tmp_path)
        for _ in range(view.MAX_CONCURRENT_UPLOADS):
            await view._slots.acquire()
        response = await asyncio.wait_for(view.post(_request("uid-kid")), timeout=1)
        assert response.status == 429
        assert not (tmp_path / photos.PHOTOS_DIR).exists()

    run(go())


# ── 4. a restored backup keeps this instance's routing and devices ──────────


def _crafted_routing():
    return {
        "children": [
            {"id": "c1", "name": "Mia", "notify_service": "notify.mobile_app_attacker", "is_adult": True},
            {"id": "c2", "name": "New kid", "notify_service": "notify.mobile_app_attacker", "is_adult": True},
        ],
        "parent_recipients": [{"id": "p9", "name": "Them", "notify_service": "notify.mobile_app_attacker"}],
        "settings": {
            "screen_time_devices": {"c1": ["switch.attacker_relay"]},
            "boost_wake_screens": ["media_player.attacker"],
            "boost_wake_devices": ["mobile_app_attacker"],
        },
    }


def test_import_keeps_this_instances_parent_recipients_and_devices():
    async def go():
        s = await _storage()
        s._data["parent_recipients"] = [{"id": "p1", "name": "Mum", "notify_service": "notify.mobile_app_mum"}]
        s.set_setting("screen_time_devices", {"c1": ["switch.tv"]})
        s.set_setting("boost_wake_screens", ["media_player.kitchen"])
        s.set_setting("boost_wake_devices", ["mobile_app_mums_phone"])

        s.import_data(_crafted_routing())

        assert [r["notify_service"] for r in s._data["parent_recipients"]] == ["notify.mobile_app_mum"]
        assert s.get_setting("screen_time_devices") == {"c1": ["switch.tv"]}
        assert s.get_setting("boost_wake_screens") == ["media_player.kitchen"]
        assert s.get_setting("boost_wake_devices") == ["mobile_app_mums_phone"]

    run(go())


def test_import_keeps_each_known_childs_notify_service_and_adult_flag():
    async def go():
        s = await _storage()
        s.add_child(Child(name="Mia", id="c1", notify_service="notify.mobile_app_mia", is_adult=False))

        s.import_data(_crafted_routing())

        kids = {c.id: c for c in s.get_children()}
        assert kids["c1"].notify_service == "notify.mobile_app_mia"
        assert kids["c1"].is_adult is False
        # A child this instance has never seen arrives with no device and no
        # auto-approval: a parent sets both on the instance that uses them.
        assert kids["c2"].notify_service == ""
        assert kids["c2"].is_adult is False

    run(go())


def test_import_on_a_fresh_instance_routes_nothing_anywhere():
    async def go():
        s = await _storage()
        s.import_data(_crafted_routing())
        assert s._data["parent_recipients"] == []
        assert s.get_setting("screen_time_devices", None) is None
        assert s.get_setting("boost_wake_screens", None) is None
        assert s.get_setting("boost_wake_devices", None) is None
        assert all(c.notify_service == "" and c.is_adult is False for c in s.get_children())

    run(go())


def test_round_trip_keeps_the_instances_own_routing():
    async def go():
        s = await _storage()
        s.add_child(Child(name="Mia", id="c1", notify_service="notify.mobile_app_mia", is_adult=True))
        s._data["parent_recipients"] = [{"id": "p1", "name": "Mum", "notify_service": "notify.mobile_app_mum"}]
        s.set_setting("screen_time_devices", {"c1": ["switch.tv"]})
        s.import_data(s.export_data())
        assert s.get_children()[0].notify_service == "notify.mobile_app_mia"
        assert s.get_children()[0].is_adult is True
        assert s._data["parent_recipients"][0]["id"] == "p1"
        assert s.get_setting("screen_time_devices") == {"c1": ["switch.tv"]}

    run(go())


# ── 5. routine entries never push a denied attempt off the end ──────────────


def test_six_hundred_routine_entries_do_not_evict_an_earlier_denied_one():
    async def go():
        s = await _storage()
        s.add_audit_entry(
            {
                "id": "denied",
                "ts": "2026-10-25T09:00:00+00:00",
                "user_id": "kid",
                "action": "service.gift_points (denied)",
                "target": "Mia",
            }
        )
        # Each line differs in target so none fold into the one before it.
        for i in range(600):
            s.add_audit_entry(
                {
                    "id": str(i),
                    "ts": f"2026-10-25T10:{(i // 60) % 60:02d}:{i % 60:02d}+00:00",
                    "user_id": "kid",
                    "action": "service.complete_chore",
                    "target": f"chore_id={i}",
                }
            )
        log = s._data["audit_log"]
        assert len(log) == 500
        assert "denied" in {e["id"] for e in log}
        assert s.get_audit_dropped_count() == 101
        # The routine lines that went were the oldest ones.
        routine = [e["id"] for e in log if e["id"] != "denied"]
        assert routine == [str(i) for i in range(101, 600)]

    run(go())


def test_denied_entries_alone_still_trim_once_they_exceed_the_cap():
    async def go():
        s = await _storage()
        for i in range(520):
            s.add_audit_entry(
                {
                    "id": str(i),
                    "ts": "2026-10-25T10:00:00+00:00",
                    "user_id": "kid",
                    "action": "service.gift_points (denied)",
                    "target": f"chore_id={i}",
                }
            )
        log = s._data["audit_log"]
        assert len(log) == 500 and log[0]["id"] == "20"
        assert s.get_audit_dropped_count() == 20

    run(go())


# ── 6 + 7. services: gated, audited, rate-limited, unregistered ─────────────


async def _services(user=None, parent_ids=(), child=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.async_record_audit = AsyncMock()
    coord.get_child = MagicMock(return_value=child)
    coord.storage = MagicMock()
    coord.storage.get_parent_user_ids = MagicMock(return_value=list(parent_ids))
    coord.storage.get_children = MagicMock(return_value=[child] if child else [])
    coord.storage.get_require_linked_child = MagicMock(return_value=False)
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    hass.auth.async_get_user = AsyncMock(return_value=user)
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    await tm._async_register_services(hass)
    registered = {c.args[1]: c.args[2] for c in hass.services.async_register.call_args_list}
    return hass, coord, registered


def _call(service, user_id, **data):
    call = MagicMock()
    call.context.user_id = user_id
    call.service = service
    call.data = data
    return call


def _denied_actions(coord):
    return [c.args[2] for c in coord.async_record_audit.await_args_list if c.args[2].endswith("(denied)")]


@pytest.mark.asyncio
async def test_preview_sound_is_an_admin_action():
    hass, coord, registered = await _services(user=MagicMock(is_admin=False, name="Kid"))
    with pytest.raises(tm.Unauthorized):
        await registered["preview_sound"](_call("preview_sound", "uid-kid", sound="coin"))
    hass.bus.async_fire.assert_not_called()
    assert _denied_actions(coord) == ["service.preview_sound (denied)"]


@pytest.mark.asyncio
async def test_read_aloud_reaches_the_audit_log():
    kid = Child(name="Mia", id="c1", linked_user_id="uid-kid")
    _hass, coord, registered = await _services(user=MagicMock(is_admin=False, name="Kid"), child=kid)
    coord.async_read_aloud = AsyncMock()
    await registered["read_aloud"](_call("read_aloud", "uid-kid", child_id="c1"))
    coord.async_read_aloud.assert_awaited_once()
    assert [c.args[2] for c in coord.async_record_audit.await_args_list] == ["service.read_aloud"]


@pytest.mark.asyncio
async def test_unload_removes_every_service_setup_registered():
    hass, _coord, registered = await _services()
    tm._async_unregister_services(hass)
    removed = {c.args[1] for c in hass.services.async_remove.call_args_list}
    assert set(registered) - removed == set()


@pytest.mark.asyncio
async def test_a_child_account_is_slowed_after_a_burst_of_calls():
    kid = Child(name="Mia", id="c1", linked_user_id="uid-kid")
    _hass, coord, registered = await _services(user=MagicMock(is_admin=False, name="Kid"), child=kid)
    coord.async_set_avatar = AsyncMock()
    for _ in range(tm.CHILD_SERVICE_RATE_LIMIT):
        await registered["choose_avatar"](_call("choose_avatar", "uid-kid", child_id="c1", icon="mdi:star"))
    with pytest.raises(tm.ServiceValidationError):
        await registered["choose_avatar"](_call("choose_avatar", "uid-kid", child_id="c1", icon="mdi:star"))
    assert coord.async_set_avatar.await_count == tm.CHILD_SERVICE_RATE_LIMIT
    assert _denied_actions(coord) == ["service.choose_avatar (denied)"]


@pytest.mark.asyncio
async def test_parents_and_automations_are_not_rate_limited():
    kid = Child(name="Mia", id="c1", linked_user_id="")
    _hass, coord, registered = await _services(
        user=MagicMock(is_admin=False, name="Mum"), parent_ids=["uid-mum"], child=kid
    )
    coord.async_set_avatar = AsyncMock()
    for _ in range(tm.CHILD_SERVICE_RATE_LIMIT + 5):
        await registered["choose_avatar"](_call("choose_avatar", "uid-mum", child_id="c1", icon="mdi:star"))
    for _ in range(tm.CHILD_SERVICE_RATE_LIMIT + 5):
        await registered["choose_avatar"](_call("choose_avatar", "", child_id="c1", icon="mdi:star"))
    assert coord.async_set_avatar.await_count == 2 * (tm.CHILD_SERVICE_RATE_LIMIT + 5)
    assert _denied_actions(coord) == []


# ── 7b. help requests stay on the child's own chores ────────────────────────


_NOW_PATH = "custom_components.taskmate.coord_wellbeing.dt_util.now"


def test_help_cannot_be_requested_on_a_siblings_chore():
    from tests.test_family_care import _family, _now

    coord, storage, _mod, kid, chore = _family()
    sibling = run(coord.async_add_child("Malia"))
    chore.assigned_to = [sibling.id]
    storage.update_chore(chore)
    with patch(_NOW_PATH, return_value=_now()), pytest.raises(ValueError, match="not one of"):
        run(coord.async_request_help(kid.id, chore.id))
    assert coord.open_help_requests() == []
    coord.notifications.fire.assert_not_awaited()


def test_a_second_help_request_within_a_minute_is_refused_whatever_the_chore():
    from tests.test_family_care import _family, _now

    coord, _storage, _mod, kid, chore = _family()
    other = run(coord.async_add_chore("Feed cat", points=3, schedule_mode="specific_days"))
    with patch(_NOW_PATH, return_value=_now()):
        run(coord.async_request_help(kid.id, chore.id))
        with pytest.raises(ValueError):
            run(coord.async_request_help(kid.id, other.id))
    with patch(_NOW_PATH, return_value=_now() + dt.timedelta(seconds=tm.coord_wellbeing.HELP_COOLDOWN_SECONDS + 1)):
        run(coord.async_request_help(kid.id, other.id))
        assert [r["chore_id"] for r in coord.open_help_requests(kid.id)] == [other.id, chore.id]


# ── 8. a child's avatar is an icon or a safe picture URL ────────────────────


def _ws_child_env():
    from tests.test_setup_wizard import _ws_env

    coord = object.__new__(TaskMateCoordinator)
    coord.storage = run(_storage())
    coord.async_refresh = AsyncMock()
    coord.async_check_birthdays = AsyncMock(return_value=[])
    hass, conn = _ws_env(coord)
    return coord, hass, conn


@pytest.mark.parametrize("avatar", ["javascript:alert(1)", "http://evil.example/a.png", "//evil.example/a.png"])
def test_add_child_refuses_an_avatar_that_is_not_an_icon_or_a_safe_url(avatar):
    from custom_components.taskmate import websocket as ws

    coord, hass, conn = _ws_child_env()
    run(ws._ws_add_child(hass, conn, {"id": 1, "type": "taskmate/add_child", "name": "Isla", "avatar": avatar}))
    conn.send_error.assert_called_once()
    conn.send_result.assert_not_called()
    assert coord.storage.get_children() == []


@pytest.mark.parametrize(
    "avatar", ["mdi:account", "/local/a.png", "", "/api/image/serve/abc/512x512", "https://x/a.png"]
)
def test_add_child_accepts_icons_and_safe_picture_urls(avatar):
    from custom_components.taskmate import websocket as ws

    coord, hass, conn = _ws_child_env()
    run(ws._ws_add_child(hass, conn, {"id": 1, "type": "taskmate/add_child", "name": "Isla", "avatar": avatar}))
    conn.send_error.assert_not_called()
    conn.send_result.assert_called_once()
    assert coord.storage.get_children()[0].avatar == (avatar or "mdi:account-circle")


def test_update_child_applies_the_same_avatar_rule():
    from custom_components.taskmate import websocket as ws

    coord, hass, conn = _ws_child_env()
    coord.storage.add_child(Child(name="Isla", id="k1", avatar="mdi:star"))
    coord.async_update_child = AsyncMock()
    run(
        ws._ws_update_child(
            hass, conn, {"id": 2, "type": "taskmate/update_child", "child_id": "k1", "avatar": "javascript:alert(1)"}
        )
    )
    conn.send_error.assert_called_once()
    coord.async_update_child.assert_not_awaited()
    assert coord.storage.get_child("k1").avatar == "mdi:star"
    run(
        ws._ws_update_child(
            hass, conn, {"id": 3, "type": "taskmate/update_child", "child_id": "k1", "avatar": "/local/a.png"}
        )
    )
    conn.send_result.assert_called_once()
    assert coord.async_update_child.await_args.args[0].avatar == "/local/a.png"


# ── 2b. the serve views refuse a laundered name before touching the disk ────
# aiohttp decodes ``%0A`` in a path segment, so ``…png\n`` does reach the
# view's ``filename``. ``re.match`` with ``$`` lets it through; the file never
# exists, so the result was a 404 either way — but the disk should not be
# consulted for a name that failed the pattern.

from custom_components.taskmate import http_images, http_sounds  # noqa: E402


@pytest.mark.parametrize(
    ("view_cls", "module", "path_fn", "name"),
    [
        (http_images.TaskMateImageServeView, images, "images_path", "a" * 32 + ".png\n"),
        (http_sounds.TaskMateSoundServeView, sounds, "sounds_path", "a" * 32 + ".mp3\n"),
    ],
)
def test_serve_views_refuse_a_trailing_newline_before_any_disk_access(monkeypatch, view_cls, module, path_fn, name):
    def _never(_hass):
        raise AssertionError("the disk was consulted for a name that failed the pattern")

    monkeypatch.setattr(module, path_fn, _never)
    response = run(view_cls(MagicMock()).get(MagicMock(), name))
    assert response.status == 404
