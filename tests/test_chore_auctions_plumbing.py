"""Chore auctions: the surfaces around the coordinator (#982).

The auction itself is covered in test_chore_auctions.py. What breaks silently
is everything either side of it — above all, the secrecy of the bids: the
WebSocket view a child's card fetches, the sensor digest anyone can read, and
the events on the bus must never carry another child's amount. Plus the
plumbing: the card is registered, the sensor reaches the resolver, the chores
slice carries the win the cards filter on, and every new string is translated.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate import websocket_auctions as wsa
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES_BY_ID

from .conftest import dt_util_mock
from .test_chore_auctions import CLOSES, NOW, TOMORROW, _chore, _coord, _numbers

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
LOCALES = INTEGRATION / "www" / "locales"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def _auction_with_bids(coord):
    auction = run(coord.async_start_auction("c1", TOMORROW, 40, CLOSES, eligible_child_ids=["k1", "k2"]))
    run(coord.async_place_bid(auction.id, "k1", 31))
    run(coord.async_place_bid(auction.id, "k2", 17))
    return auction


def _wired(**users):
    """A coordinator reachable from the WebSocket layer, with HA users."""
    coord = _coord()
    coord.hass.data = {DOMAIN: {"entry": coord}}
    known = {uid: SimpleNamespace(id=uid, is_admin=admin) for uid, admin in users.items()}
    coord.hass.auth.async_get_user = AsyncMock(side_effect=lambda uid: known.get(uid))
    return coord


def _conn(user_id, admin=False):
    connection = MagicMock()
    connection.user = SimpleNamespace(id=user_id, is_admin=admin)
    return connection


# ── the card's WebSocket view ────────────────────────────────────────────────


def test_a_childs_view_has_their_own_bid_and_never_a_siblings():
    coord = _wired(u_kid=False)
    _auction_with_bids(coord)
    connection = _conn("u_kid")
    run(wsa.ws_auctions_list(coord.hass, connection, {"id": 1, "type": wsa.WS_AUCTIONS_LIST, "child_id": "k1"}))
    result = connection.send_result.call_args.args[1]
    assert result["auctions"][0]["my_bid"] == 31 and result["auctions"][0]["bid_count"] == 2
    assert 17 not in _numbers(result)


def test_a_child_linked_to_someone_else_cannot_read_the_view_or_bid():
    coord = _wired(u_vaiha=False)
    auction = _auction_with_bids(coord)
    coord.storage.data["children"][0]["linked_user_id"] = "u_malia"
    coord.storage.data["children"][1]["linked_user_id"] = "u_vaiha"
    connection = _conn("u_vaiha")
    run(wsa.ws_auctions_list(coord.hass, connection, {"id": 1, "type": wsa.WS_AUCTIONS_LIST, "child_id": "k1"}))
    assert connection.send_error.called and not connection.send_result.called
    connection = _conn("u_vaiha")
    msg = {"id": 2, "type": wsa.WS_AUCTIONS_BID, "auction_id": auction.id, "child_id": "k1", "points": 1}
    run(wsa.ws_auctions_bid(coord.hass, connection, msg))
    assert connection.send_error.called
    assert coord.storage.get_auction(auction.id).bids["k1"]["points"] == 31


def test_only_a_parent_gets_the_amounts():
    coord = _wired(u_kid=False, u_mum=False, u_admin=True)
    _auction_with_bids(coord)
    coord.storage.set_parent_user_ids(["u_mum"])
    msg = {"id": 1, "type": wsa.WS_AUCTIONS_LIST}
    connection = _conn("u_kid")
    run(wsa.ws_auctions_list(coord.hass, connection, msg))
    assert connection.send_error.called and not connection.send_result.called
    for user, admin in (("u_mum", False), ("u_admin", True)):
        connection = _conn(user, admin)
        run(wsa.ws_auctions_list(coord.hass, connection, msg))
        bids = connection.send_result.call_args.args[1]["auctions"][0]["bids"]
        assert [(b["child_id"], b["points"]) for b in bids] == [("k2", 17), ("k1", 31)]


def test_bidding_over_the_websocket_reports_a_refusal_cleanly():
    coord = _wired(u_kid=False)
    auction = _auction_with_bids(coord)
    connection = _conn("u_kid")
    msg = {"id": 1, "type": wsa.WS_AUCTIONS_BID, "auction_id": auction.id, "child_id": "k3", "points": 5}
    run(wsa.ws_auctions_bid(coord.hass, connection, msg))
    assert connection.send_error.call_args.args[1] == "invalid"


def test_the_panel_commands_are_admin_only():
    coord = _wired(u_mum=False)
    connection = _conn("u_mum")
    msg = {
        "id": 1,
        "type": wsa.WS_AUCTIONS_START,
        "chore_id": "c1",
        "occurrence": TOMORROW,
        "max_points": 12,
        "closes_at": CLOSES,
        "min_points": 1,
        "notify_children": True,
    }
    run(wsa.ws_auctions_start(coord.hass, connection, msg))
    assert connection.send_error.called and coord.storage.get_auctions() == []
    connection = _conn("u_admin", admin=True)
    run(wsa.ws_auctions_start(coord.hass, connection, msg))
    assert connection.send_result.called and len(coord.storage.get_auctions()) == 1


def test_the_occurrence_lookup_offers_dates_the_pool_and_the_normal_price():
    coord = _wired()
    connection = _conn("u_admin", admin=True)
    run(wsa.ws_auctions_occurrences(coord.hass, connection, {"id": 1, "type": "x", "chore_id": "c1"}))
    result = connection.send_result.call_args.args[1]
    assert result["occurrences"][0] == TOMORROW and result["refusal"] == ""
    assert result["pool"] == ["k1", "k2", "k3"] and result["normal_points"] == 6


def test_every_command_is_registered():
    source = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    assert "AUCTION_COMMANDS" in source.split("def async_register_websocket_commands")[1]
    assert len(wsa.AUCTION_COMMANDS) == 7


def test_the_panel_snapshot_carries_the_auctions():
    coord = _coord()
    _auction_with_bids(coord)
    snapshot = ws._build_state_snapshot(coord)
    assert snapshot["auctions"][0]["bids"][0]["points"] == 17


# ── the sensor digest and the bus ────────────────────────────────────────────


def test_the_auctions_sensor_publishes_counts_not_amounts():
    coord = _coord()
    auction = _auction_with_bids(coord)
    coord.data = {}
    sensor = sensor_module.TaskMateAuctionsSensor(coord, SimpleNamespace(entry_id="e1"))
    attrs = sensor._build_attributes()
    assert attrs["auctions"][0]["bids"] == 2 and attrs["auctions"][0]["id"] == auction.id
    assert not {31, 17} & _numbers(attrs)
    assert sensor.native_value == 1
    assert "auctions" in sensor._unrecorded_attributes


def test_no_event_ever_carries_a_bid_amount():
    coord = _coord()
    auction = _auction_with_bids(coord)
    run(coord.async_withdraw_bid(auction.id, "k1"))
    for call in coord.hass.bus.async_fire.call_args_list:
        assert 31 not in call.args[1].values() and 17 not in call.args[1].values(), call.args[0]


# ── the chores slice the cards filter on ─────────────────────────────────────


def _chores_slice(coord):
    data = {"chores": coord.storage.get_chores(), "children": coord.storage.get_children()}
    coord.data = data
    common = {"chores": data["chores"], "hass": coord.hass}
    return {c["id"]: c for c in sensor_module._build_chores_list(coord, common)}


def test_the_chores_slice_carries_todays_win_and_the_weeks_wins():
    coord = _coord([_chore(points=6)])
    auction = run(coord.async_start_auction("c1", TOMORROW, 40, CLOSES))
    run(coord.async_place_bid(auction.id, "k2", 9))
    run(coord.async_close_auction(auction.id))
    record = _chores_slice(coord)["c1"]
    assert record["auction_wins"] == {TOMORROW: "k2"} and "auction" not in record
    dt_util_mock._now = NOW + dt.timedelta(days=1)
    record = _chores_slice(coord)["c1"]
    assert record["auction"] == {"child_id": "k2", "points": 9}
    assert record["effective_points"] == 9


def test_an_ordinary_chore_carries_nothing_extra():
    record = _chores_slice(_coord())["c1"]
    assert "auction" not in record and "auction_wins" not in record


# ── registration and strings ─────────────────────────────────────────────────


def test_the_card_is_registered_and_shipped():
    assert '"taskmate-auction-card.js",' in (INTEGRATION / "frontend.py").read_text(encoding="utf-8")
    assert (INTEGRATION / "www" / "taskmate-auction-card.js").is_file()


def test_the_resolver_merges_the_auctions_sensor():
    source = (INTEGRATION / "www" / "taskmate-attr-resolver.js").read_text(encoding="utf-8")
    assert '"sensor.taskmate_auctions"' in source


@pytest.mark.parametrize("type_id", ["auction_opened", "auction_closing", "auction_result"])
def test_notification_types_are_opt_in_and_labelled_everywhere(type_id):
    meta = NOTIFICATION_TYPES_BY_ID[type_id]
    assert meta.default_enabled is False
    for path in LOCALES.glob("*.json"):
        strings = json.loads(path.read_text(encoding="utf-8"))
        assert strings.get(f"notification.{type_id}.name"), path.name
        assert strings.get(f"notification.{type_id}.description"), path.name


def test_every_auction_string_the_ui_uses_exists_in_english():
    import re

    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    www = INTEGRATION / "www"
    used = set()
    for name in ("taskmate-auction-card.js", "taskmate-panel.js", "taskmate-child-card.js"):
        source = (www / name).read_text(encoding="utf-8")
        used |= set(re.findall(r'_t\(\s*"((?:auction\.|panel\.auction_|panel\.toast_auction_)[\w.]+)"', source))
    used |= {f"panel.auction_col_{c}" for c in ("chore", "max", "who", "bids", "closes", "result", "status")}
    used |= {f"panel.auction_sec_{s}" for s in ("chore", "price", "bidding")}
    used |= {"child.won_at_auction", "panel.tab_auctions", "panel.new_auction"}
    missing = sorted(k for k in used if k not in en)
    assert not missing, missing
