"""Kiosk mode (#930): PIN hashing, rate limiting, storage and the WS commands.

The kiosk card runs on a shared tablet under one (usually non-admin) Home
Assistant account. What must hold on the backend:

* a PIN is only ever stored as a salted hash, and never leaves the server —
  not in get_state, not in the child records;
* verify_pin can't be used to walk the 10,000 possible PINs quickly;
* status tells the card, per child, whether this user may act for them, using
  the same linked-child rule the complete path enforces — so a kiosk never
  offers buttons that would be refused, and never bypasses the rule.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import kiosk
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child
from custom_components.taskmate.storage import TaskMateStorage

# ── hashing ─────────────────────────────────────────────────────────────────


def test_hash_round_trips_and_rejects_other_pins():
    stored = kiosk.hash_pin("1234", iterations=1000)
    assert kiosk.verify_pin_hash("1234", stored) is True
    assert kiosk.verify_pin_hash("4321", stored) is False
    assert kiosk.verify_pin_hash("12345", stored) is False


def test_hash_is_salted_and_never_contains_the_pin():
    a = kiosk.hash_pin("1234", iterations=1000)
    b = kiosk.hash_pin("1234", iterations=1000)
    assert a != b  # fresh salt each time
    assert a.startswith("pbkdf2_sha256$1000$")
    assert "1234" not in a.split("$", 2)[2]


def test_hash_refuses_a_malformed_pin():
    for bad in ("", "123", "12345", "12a4", "１２３４", " 123", "1234\n"):
        with pytest.raises(ValueError):
            kiosk.hash_pin(bad)


@pytest.mark.parametrize(
    "stored",
    [None, "", "garbage", "md5$1$00$00", "pbkdf2_sha256$x$00$00", "pbkdf2_sha256$1000$zz$00", 42],
)
def test_malformed_stored_hash_never_matches(stored):
    assert kiosk.verify_pin_hash("1234", stored) is False


# ── rate limiting ───────────────────────────────────────────────────────────


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_five_wrong_tries_lock_the_pad_for_thirty_seconds():
    clock = _Clock()
    limiter = kiosk.PinRateLimiter(clock)
    for _ in range(kiosk.MAX_FAILURES - 1):
        assert limiter.begin_attempt("malia") == 0
    assert limiter.attempts_left("malia") == 1
    assert limiter.begin_attempt("malia") == 0  # the fifth try is still checked
    assert limiter.locked_for("malia") == kiosk.BASE_LOCK_SECONDS
    assert limiter.begin_attempt("malia") == kiosk.BASE_LOCK_SECONDS  # refused outright
    clock.now += kiosk.BASE_LOCK_SECONDS
    assert limiter.locked_for("malia") == 0
    assert limiter.begin_attempt("malia") == 0


def test_each_lockout_is_longer_up_to_the_cap():
    clock = _Clock()
    limiter = kiosk.PinRateLimiter(clock)
    seen = []
    for _ in range(8):
        for _ in range(kiosk.MAX_FAILURES):
            limiter.begin_attempt("malia")
        seen.append(limiter.locked_for("malia"))
        clock.now += seen[-1]
    assert seen[:4] == [30, 60, 120, 240]
    assert max(seen) == kiosk.MAX_LOCK_SECONDS


def test_locks_are_per_child_and_a_right_pin_clears_them():
    limiter = kiosk.PinRateLimiter(_Clock())
    for _ in range(kiosk.MAX_FAILURES):
        limiter.begin_attempt("malia")
    assert limiter.locked_for("malia") > 0
    assert limiter.locked_for("vaiha") == 0
    limiter.reset("malia")
    assert limiter.locked_for("malia") == 0
    assert limiter.attempts_left("malia") == kiosk.MAX_FAILURES


# ── storage ─────────────────────────────────────────────────────────────────


async def _storage(hass) -> TaskMateStorage:
    storage = TaskMateStorage(hass, "kiosk_test")
    await storage.async_load()
    return storage


async def test_storage_keeps_pins_apart_from_the_child_record(hass):
    storage = await _storage(hass)
    storage.add_child(Child(name="Malia", id="malia"))
    storage.set_kiosk_pin_hash("malia", "pbkdf2_sha256$1$00$00")
    assert storage.get_kiosk_pin_hash("malia") == "pbkdf2_sha256$1$00$00"
    assert storage.get_kiosk_pin_child_ids() == ["malia"]
    assert "pbkdf2" not in json.dumps(storage.data["children"])
    storage.set_kiosk_pin_hash("malia", "")
    assert storage.get_kiosk_pin_hash("malia") == ""
    assert "kiosk_pins" not in storage.data


async def test_old_or_damaged_data_reads_as_no_pins(hass):
    storage = await _storage(hass)
    assert storage.get_kiosk_pin_child_ids() == []
    storage.data["kiosk_pins"] = ["not", "a", "dict"]
    assert storage.get_kiosk_pin_hash("malia") == ""
    storage.data["kiosk_pins"] = {"malia": 7, "vaiha": "hash"}
    assert storage.get_kiosk_pin_hash("malia") == ""
    assert storage.get_kiosk_pin_child_ids() == ["vaiha"]


async def test_removing_a_child_drops_their_pin(hass):
    storage = await _storage(hass)
    storage.add_child(Child(name="Malia", id="malia"))
    storage.set_kiosk_pin_hash("malia", "hash")
    storage.remove_child("malia")
    assert storage.get_kiosk_pin_hash("malia") == ""


# ── WebSocket commands ──────────────────────────────────────────────────────


async def _executor(func, *args):
    return func(*args)


@pytest.fixture
async def setup(hass):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.entry_id = "kiosk_test"
    coord.storage = await _storage(hass)
    coord.storage.add_child(Child(name="Malia", id="malia"))
    coord.storage.add_child(Child(name="Vaiha", id="vaiha", linked_user_id="uid-vaiha"))
    coord.get_due_chores_for_child = lambda cid: [MagicMock(id=f"{cid}-dishes")]
    hass.data = {DOMAIN: {"kiosk_test": coord}}
    hass.async_add_executor_job = _executor
    hass.auth = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=MagicMock(is_admin=False))
    return coord


def _connection(user_id="uid-tablet", is_admin=False) -> MagicMock:
    connection = MagicMock()
    connection.user.id = user_id
    connection.user.is_admin = is_admin
    return connection


def _result(connection):
    connection.send_error.assert_not_called()
    args, _ = connection.send_result.call_args
    return args[1]


def _by_id(result):
    return {c["id"]: c for c in result["children"]}


async def test_status_serves_a_non_admin_tablet(setup, hass):
    setup.storage.set_kiosk_pin_hash("malia", kiosk.hash_pin("1234", iterations=1000))
    conn = _connection()
    await kiosk.ws_kiosk_status(hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_STATUS})
    kids = _by_id(_result(conn))
    assert kids["malia"] == {"id": "malia", "has_pin": True, "can_act": True, "due": ["malia-dishes"]}
    # Vaiha is linked to her own account, so the tablet may not act for her.
    assert kids["vaiha"]["has_pin"] is False
    assert kids["vaiha"]["can_act"] is False
    assert "pbkdf2" not in json.dumps(_result(conn))


async def test_status_honours_require_linked_child(setup, hass):
    setup.storage.data.setdefault("settings", {})["require_linked_child"] = True
    conn = _connection()
    await kiosk.ws_kiosk_status(hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_STATUS})
    assert _by_id(_result(conn))["malia"]["can_act"] is False

    # A TaskMate parent's account on the tablet may still act for any child.
    setup.storage.data["settings"]["parent_user_ids"] = ["uid-tablet"]
    conn = _connection()
    await kiosk.ws_kiosk_status(hass, conn, {"id": 2, "type": kiosk.WS_KIOSK_STATUS})
    assert _by_id(_result(conn))["malia"]["can_act"] is True


async def test_status_lets_an_admin_act_for_everyone(setup, hass):
    hass.auth.async_get_user = AsyncMock(return_value=MagicMock(is_admin=True))
    conn = _connection("uid-admin", is_admin=True)
    await kiosk.ws_kiosk_status(hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_STATUS})
    assert all(c["can_act"] for c in _result(conn)["children"])


async def _verify(hass, pin, child_id="malia"):
    conn = _connection()
    await kiosk.ws_kiosk_verify_pin(
        hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_VERIFY_PIN, "child_id": child_id, "pin": pin}
    )
    return _result(conn)


async def test_verify_pin(setup, hass):
    setup.storage.set_kiosk_pin_hash("malia", kiosk.hash_pin("1234", iterations=1000))
    assert await _verify(hass, "1234") == {"ok": True}
    miss = await _verify(hass, "0000")
    assert miss == {"ok": False, "locked_for": 0, "attempts_left": kiosk.MAX_FAILURES - 1}


async def test_verify_pin_without_a_pin_set_lets_the_child_in(setup, hass):
    assert await _verify(hass, "", child_id="vaiha") == {"ok": True}


async def test_verify_pin_locks_after_repeated_misses_even_for_the_right_pin(setup, hass):
    setup.storage.set_kiosk_pin_hash("malia", kiosk.hash_pin("1234", iterations=1000))
    for _ in range(kiosk.MAX_FAILURES - 1):
        await _verify(hass, "0000")
    last = await _verify(hass, "9999")
    assert last["ok"] is False and last["locked_for"] == kiosk.BASE_LOCK_SECONDS
    # Locked: even the right PIN is refused until the lock runs out.
    assert (await _verify(hass, "1234"))["ok"] is False


async def test_verify_pin_unknown_child(setup, hass):
    conn = _connection()
    await kiosk.ws_kiosk_verify_pin(hass, conn, {"id": 1, "type": "x", "child_id": "nobody", "pin": "1234"})
    assert conn.send_error.call_args[0][1] == "not_found"


async def test_set_pin_is_admin_only(setup, hass):
    conn = _connection()
    await kiosk.ws_kiosk_set_pin(
        hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_SET_PIN, "child_id": "malia", "pin": "1234"}
    )
    assert conn.send_error.call_args[0][1] == ws.websocket_api.const.ERR_UNAUTHORIZED
    assert setup.storage.get_kiosk_pin_hash("malia") == ""


async def test_set_pin_stores_a_hash_and_clears_it(setup, hass):
    setup.async_record_audit = AsyncMock()
    conn = _connection("uid-admin", is_admin=True)
    await kiosk.ws_kiosk_set_pin(
        hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_SET_PIN, "child_id": "malia", "pin": "2468"}
    )
    assert _result(conn) == {"id": "malia", "has_pin": True}
    stored = setup.storage.get_kiosk_pin_hash("malia")
    assert stored.startswith("pbkdf2_sha256$") and kiosk.verify_pin_hash("2468", stored)

    conn = _connection("uid-admin", is_admin=True)
    await kiosk.ws_kiosk_set_pin(hass, conn, {"id": 2, "type": kiosk.WS_KIOSK_SET_PIN, "child_id": "malia", "pin": ""})
    assert _result(conn) == {"id": "malia", "has_pin": False}
    assert setup.storage.get_kiosk_pin_hash("malia") == ""


@pytest.mark.parametrize("pin", ["123", "abcd", "12345"])
async def test_set_pin_rejects_anything_but_four_digits(setup, hass, pin):
    setup.async_record_audit = AsyncMock()
    conn = _connection("uid-admin", is_admin=True)
    await kiosk.ws_kiosk_set_pin(hass, conn, {"id": 1, "type": kiosk.WS_KIOSK_SET_PIN, "child_id": "malia", "pin": pin})
    assert conn.send_error.call_args[0][1] == "invalid_format"
    assert setup.storage.get_kiosk_pin_hash("malia") == ""


async def test_get_state_says_who_has_a_pin_but_never_the_hash(setup):
    setup.storage.set_kiosk_pin_hash("malia", kiosk.hash_pin("1234", iterations=1000))
    setup.avatar_catalog = lambda: []
    setup.get_all_templates = lambda: []
    setup.mandatory_misses_state = lambda: []
    setup.custom_sounds_state = lambda: []
    snapshot = ws._build_state_snapshot(setup)
    assert snapshot["kiosk_pin_children"] == ["malia"]
    assert "pbkdf2" not in json.dumps(snapshot, default=str)


def test_kiosk_commands_are_registered():
    registered = MagicMock()
    hass = MagicMock()
    hass.data = {}
    original = ws.websocket_api.async_register_command
    ws.websocket_api.async_register_command = registered
    try:
        ws.async_register_websocket_commands(hass)
    finally:
        ws.websocket_api.async_register_command = original
    handlers = {call.args[1] for call in registered.call_args_list}
    assert set(kiosk.KIOSK_COMMANDS) <= handlers
