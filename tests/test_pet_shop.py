"""Pet shop: fixed-cost cosmetics, parent approvals, the wardrobe and its sensor shape."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.models import PointsTransaction

from .test_completion_eligibility import _make_system, _now, run

PETS = "custom_components.taskmate.coord_pets.dt_util"
SHOP = "custom_components.taskmate.coord_pet_shop.dt_util.now"


def _setup(points=100, *, shop=True, adopt=True, level=1):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    storage.set_setting("pets_enabled", True)
    storage.set_setting("pet_shop_enabled", shop)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Malia"))
        other = run(coord.async_add_child("Vaiha"))
    for c in (kid, other):
        c = storage.get_child(c.id)
        c.points = points
        c.level = level
        storage.update_child(c)
    if adopt:
        with patch(f"{PETS}.now", return_value=_now()), patch(f"{PETS}.as_local", side_effect=lambda d: d):
            run(coord.async_adopt_pet(kid.id, "dragon", "Sparky"))
    return coord, storage, storage.get_child(kid.id), storage.get_child(other.id)


def _buy(coord, child_id, item_id):
    with patch(SHOP, return_value=_now()):
        return run(coord.async_buy_pet_item(child_id, item_id))


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args and c.args[0] == name]


# ── catalogue ───────────────────────────────────────────────────────────────


class TestCatalogue:
    def test_default_catalogue_matches_the_mockup(self):
        coord, *_ = _setup()
        items = {i["id"]: i for i in coord.pet_shop_items()}
        assert [(i, items[i]["slot"], items[i]["cost"]) for i in items] == [
            ("sunglasses", "face", 15),
            ("cap", "hat", 20),
            ("balloon", "held", 25),
            ("cosy_bed", "home", 40),
            ("rainbow", "colour", 60),
            ("wings", "back", 80),
            ("ghost_sheet", "body", 30),
        ]
        assert items["wings"]["level"] == 12
        assert items["ghost_sheet"]["shown"] is False
        assert all(i["shown"] for k, i in items.items() if k != "ghost_sheet")

    def test_add_edit_hide_remove_and_reset(self):
        coord, storage, *_ = _setup()
        item = run(coord.async_save_pet_shop_item(None, name="Party hat", emoji="🥳", slot="hat", cost=12))
        assert coord._pet_shop_item(item["id"])["cost"] == 12
        run(coord.async_save_pet_shop_item(item["id"], name="Party hat", emoji="🎉", slot="hat", cost=14, level=3))
        saved = coord._pet_shop_item(item["id"])
        assert (saved["emoji"], saved["cost"], saved["level"]) == ("🎉", 14, 3)
        run(coord.async_set_pet_shop_item_shown(item["id"], False))
        assert coord._pet_shop_item(item["id"])["shown"] is False
        run(coord.async_remove_pet_shop_item(item["id"]))
        assert coord._pet_shop_item(item["id"]) is None
        run(coord.async_remove_pet_shop_item("cap"))
        assert coord._pet_shop_item("cap") is None
        run(coord.async_reset_pet_shop_items())
        assert [i["id"] for i in coord.pet_shop_items()][:2] == ["sunglasses", "cap"]

    def test_default_items_can_be_renamed_and_keep_a_blank_name(self):
        coord, *_ = _setup()
        run(coord.async_save_pet_shop_item("cap", name="", emoji="🧢", slot="hat", cost=25))
        assert coord.pet_item_name(coord._pet_shop_item("cap")) == "Cap"
        run(coord.async_save_pet_shop_item("cap", name="Baseball cap", emoji="🧢", slot="hat", cost=25))
        assert coord.pet_item_name(coord._pet_shop_item("cap")) == "Baseball cap"

    @pytest.mark.parametrize(
        ("fields", "match"),
        [
            ({"name": "", "emoji": "🎩", "slot": "hat", "cost": 5}, "name"),
            ({"name": "x" * 31, "emoji": "🎩", "slot": "hat", "cost": 5}, "30"),
            ({"name": "Hat", "emoji": "", "slot": "hat", "cost": 5}, "emoji"),
            ({"name": "Hat", "emoji": "<script>", "slot": "hat", "cost": 5}, "emoji"),
            ({"name": "Hat", "emoji": "🎩" * 9, "slot": "hat", "cost": 5}, "emoji"),
            ({"name": "Hat", "emoji": "🎩", "slot": "tail", "cost": 5}, "slot"),
            ({"name": "Hat", "emoji": "🎩", "slot": "hat", "cost": 0}, "cost"),
            ({"name": "Hat", "emoji": "🎩", "slot": "hat", "cost": 100_001}, "cost"),
            ({"name": "Hat", "emoji": "🎩", "slot": "hat", "cost": 5, "level": -1}, "level"),
            ({"name": "Dye", "emoji": "🎨", "slot": "colour", "cost": 5, "tint": "red"}, "colour"),
        ],
    )
    def test_invalid_items_are_refused(self, fields, match):
        coord, *_ = _setup()
        with pytest.raises(ValueError, match=match):
            run(coord.async_save_pet_shop_item(None, **fields))

    def test_colour_tint_is_kept_only_for_colour_items(self):
        coord, *_ = _setup()
        dye = run(coord.async_save_pet_shop_item(None, name="Dye", emoji="🎨", slot="colour", cost=5, tint="#FF8800"))
        hat = run(coord.async_save_pet_shop_item(None, name="Hat", emoji="🎩", slot="hat", cost=5, tint="#ff8800"))
        assert dye["tint"] == "#ff8800" and hat["tint"] == ""

    def test_storage_round_trip(self):
        coord, storage, kid, _ = _setup()
        run(coord.async_save_pet_shop_item(None, name="Party hat", emoji="🥳", slot="hat", cost=12))
        _buy(coord, kid.id, "sunglasses")
        run(coord.async_equip_pet_item(kid.id, "sunglasses", True))
        storage.set_setting("pet_shop_approve_over", 10)
        _buy(coord, kid.id, "cap")
        run(storage.async_save())
        raw = json.loads(json.dumps(storage._store._data))
        from custom_components.taskmate.storage import TaskMateStorage
        from tests.conftest import FakeStore

        again = TaskMateStorage.__new__(TaskMateStorage)
        again.entry_id = "test_entry"
        again._store = FakeStore(None, 1, "test")
        again._store._data = raw
        again._data = {}
        run(again.async_load())
        coord.storage = again
        assert len(coord.pet_shop_items()) == 8
        assert coord.pet_owned(kid.id) == ["sunglasses"]
        assert coord.pet_worn(again.get_child(kid.id))["face"] == {"id": "sunglasses", "emoji": "🕶️"}
        assert [p["item_id"] for p in coord.pet_shop_pending_state()] == ["cap"]
        assert again.get_setting("pet_shop_enabled") is True


# ── buying ──────────────────────────────────────────────────────────────────


class TestBuying:
    def test_happy_path_spends_the_wallet_and_logs_it(self):
        coord, storage, kid, _ = _setup(points=50)
        assert _buy(coord, kid.id, "sunglasses") == {"status": "bought"}
        kid = storage.get_child(kid.id)
        assert kid.points == 35
        assert coord.pet_owned(kid.id) == ["sunglasses"]
        txn = storage.get_points_transactions()[-1]
        assert (txn.points, txn.reason) == (-15, "Pet shop: Sunglasses")
        (event,) = _fired(coord, "taskmate_pet_item_bought")
        assert event["child_id"] == kid.id and event["item_id"] == "sunglasses" and event["cost"] == 15
        # Bought, not worn: the card offers "Put on".
        assert "face" not in coord.pet_worn(kid)

    def test_wallet_only_pool_and_jars_untouched(self):
        coord, storage, kid, _ = _setup(points=20)
        kid.total_points_earned = 500
        kid.career_score = 500
        storage.update_child(kid)
        _buy(coord, kid.id, "sunglasses")
        kid = storage.get_child(kid.id)
        assert kid.points == 5
        # Spending isn't a penalty: earned totals and career score stay put.
        assert kid.total_points_earned == 500 and kid.career_score == 500
        assert kid.total_penalties_received == 0

    def test_points_promised_to_a_pending_reward_are_not_spendable(self):
        coord, storage, kid, _ = _setup(points=20)
        coord.storage.get_pending_reward_claims = lambda: [SimpleNamespace(child_id=kid.id, reward_id="r1")]
        coord.get_reward = lambda rid: SimpleNamespace(cost=10)
        coord.is_pool_mode_claim = lambda claim: False
        with pytest.raises(ValueError, match="Not enough"):
            _buy(coord, kid.id, "sunglasses")

    @pytest.mark.parametrize(
        ("prep", "item", "match"),
        [
            (lambda c, s, k: None, "nope", "isn't for sale"),
            (lambda c, s, k: run(c.async_set_pet_shop_item_shown("cap", False)), "cap", "isn't for sale"),
            (lambda c, s, k: None, "ghost_sheet", "isn't for sale"),
            (lambda c, s, k: None, "wings", "level 12"),
            (lambda c, s, k: _buy(c, k.id, "cap"), "cap", "already have"),
            (lambda c, s, k: s.set_setting("pet_shop_enabled", False), "cap", "closed"),
            (lambda c, s, k: s.set_setting("pets_enabled", False), "cap", "Pets are switched off"),
        ],
    )
    def test_refusals(self, prep, item, match):
        coord, storage, kid, _ = _setup(points=200)
        prep(coord, storage, kid)
        with pytest.raises(ValueError, match=match):
            _buy(coord, kid.id, item)

    def test_refuses_without_enough_points(self):
        coord, storage, kid, _ = _setup(points=10)
        with pytest.raises(ValueError, match="Not enough"):
            _buy(coord, kid.id, "sunglasses")
        assert storage.get_child(kid.id).points == 10
        assert coord.pet_owned(kid.id) == []

    def test_refuses_before_a_pet_is_adopted(self):
        coord, _storage, _kid, other = _setup()
        with pytest.raises(ValueError, match="Adopt"):
            _buy(coord, other.id, "cap")

    def test_level_gate_opens_at_the_level(self):
        coord, storage, kid, _ = _setup(points=200, level=12)
        assert _buy(coord, kid.id, "wings")["status"] == "bought"


# ── approvals ───────────────────────────────────────────────────────────────


class TestApproval:
    def _pending(self, points=100):
        coord, storage, kid, other = _setup(points=points)
        storage.set_setting("pet_shop_approve_over", 50)
        result = _buy(coord, kid.id, "rainbow")
        return coord, storage, kid, result

    def test_over_the_threshold_waits_for_a_parent(self):
        coord, storage, kid, result = self._pending()
        assert result["status"] == "pending"
        assert storage.get_child(kid.id).points == 100
        assert coord.pet_owned(kid.id) == []
        type_id, ctx = coord.notifications.fire.await_args.args
        assert type_id == "pet_item_requested"
        assert ctx["child_name"] == "Malia" and ctx["item_name"] == "Rainbow colour" and ctx["cost"] == 60
        assert ctx["pet_name"] == "Sparky"
        assert _fired(coord, "taskmate_pet_item_bought") == []
        (row,) = coord.pet_shop_pending_state()
        assert row["child_name"] == "Malia" and row["item_id"] == "rainbow" and row["cost"] == 60

    def test_at_or_under_the_threshold_buys_straight_away(self):
        coord, storage, kid, _ = _setup()
        storage.set_setting("pet_shop_approve_over", 15)
        assert _buy(coord, kid.id, "sunglasses")["status"] == "bought"

    def test_one_pending_purchase_per_item(self):
        coord, _storage, kid, _ = self._pending(points=200)
        with pytest.raises(ValueError, match="waiting"):
            _buy(coord, kid.id, "rainbow")

    def test_pending_points_are_spoken_for(self):
        coord, _storage, kid, _ = self._pending(points=70)
        with pytest.raises(ValueError, match="Not enough"):
            _buy(coord, kid.id, "sunglasses")

    def test_approve_deducts_then(self):
        coord, storage, kid, result = self._pending()
        with patch(SHOP, return_value=_now()):
            run(coord.async_decide_pet_purchase(result["purchase_id"], True))
        assert storage.get_child(kid.id).points == 40
        assert coord.pet_owned(kid.id) == ["rainbow"]
        assert coord.pet_shop_pending_state() == []
        assert storage.get_points_transactions()[-1].reason == "Pet shop: Rainbow colour"
        assert len(_fired(coord, "taskmate_pet_item_bought")) == 1

    def test_decline_frees_it(self):
        coord, storage, kid, result = self._pending()
        run(coord.async_decide_pet_purchase(result["purchase_id"], False))
        assert storage.get_child(kid.id).points == 100
        assert coord.pet_owned(kid.id) == []
        assert coord.pet_shop_pending_state() == []
        storage.set_setting("pet_shop_approve_over", 0)
        assert _buy(coord, kid.id, "rainbow")["status"] == "bought"

    def test_approve_refused_when_the_points_are_gone(self):
        coord, storage, kid, result = self._pending()
        kid = storage.get_child(kid.id)
        kid.points = 10
        storage.update_child(kid)
        with pytest.raises(ValueError, match="enough"):
            run(coord.async_decide_pet_purchase(result["purchase_id"], True))
        assert len(coord.pet_shop_pending_state()) == 1

    def test_unknown_purchase(self):
        coord, *_ = _setup()
        with pytest.raises(ValueError, match="waiting"):
            run(coord.async_decide_pet_purchase("nope", True))

    def test_removing_the_item_drops_its_pending_purchases(self):
        coord, _storage, _kid, _ = self._pending()
        run(coord.async_remove_pet_shop_item("rainbow"))
        assert coord.pet_shop_pending_state() == []

    def test_deleting_a_child_forgets_their_wardrobe_and_requests(self):
        coord, storage, kid, _ = self._pending()
        _buy(coord, kid.id, "sunglasses")
        storage.remove_child_from_sections(kid.id)
        assert coord.pet_owned(kid.id) == [] and coord._pet_purchases() == []


# ── wearing ─────────────────────────────────────────────────────────────────


class TestWearing:
    def test_level_accessories_are_worn_by_default_as_before(self):
        coord, storage, kid, _ = _setup(level=25)
        assert coord.pet_worn(kid) == {"hat": {"id": "crown"}, "neck": {"id": "scarf"}}
        kid.level = 8
        assert coord.pet_worn(kid) == {"hat": {"id": "top_hat"}, "neck": {"id": "bow"}}

    def test_one_item_per_slot_and_take_off(self):
        coord, storage, kid, _ = _setup(level=9)
        _buy(coord, kid.id, "cap")
        run(coord.async_equip_pet_item(kid.id, "cap", True))
        assert coord.pet_worn(kid)["hat"]["id"] == "cap"
        run(coord.async_equip_pet_item(kid.id, "top_hat", True))
        assert coord.pet_worn(kid)["hat"] == {"id": "top_hat"}
        run(coord.async_equip_pet_item(kid.id, "top_hat", False))
        assert "hat" not in coord.pet_worn(kid)
        # The bow is untouched by any of that.
        assert coord.pet_worn(kid)["neck"] == {"id": "bow"}

    def test_taking_off_something_not_worn_changes_nothing(self):
        coord, _storage, kid, _ = _setup(level=9)
        _buy(coord, kid.id, "cap")
        run(coord.async_equip_pet_item(kid.id, "cap", False))
        assert coord.pet_worn(kid)["hat"] == {"id": "top_hat"}

    def test_colour_carries_its_tint(self):
        coord, _storage, kid, _ = _setup()
        _buy(coord, kid.id, "rainbow")
        run(coord.async_equip_pet_item(kid.id, "rainbow", True))
        assert coord.pet_worn(kid)["colour"] == {"id": "rainbow", "emoji": "🌈", "tint": "rainbow"}

    @pytest.mark.parametrize(
        ("item", "match"),
        [("cap", "Buy it first"), ("crown", "unlocked"), ("nope", "isn't in the shop")],
    )
    def test_equip_refusals(self, item, match):
        coord, *_rest = _setup(level=9)
        kid = _rest[1]
        with pytest.raises(ValueError, match=match):
            run(coord.async_equip_pet_item(kid.id, item, True))

    def test_equip_needs_a_pet(self):
        coord, _storage, _kid, other = _setup(level=9)
        with pytest.raises(ValueError, match="Adopt"):
            run(coord.async_equip_pet_item(other.id, "bow", True))

    def test_a_removed_item_falls_back_to_the_level_default(self):
        coord, _storage, kid, _ = _setup(level=9)
        _buy(coord, kid.id, "cap")
        run(coord.async_equip_pet_item(kid.id, "cap", True))
        run(coord.async_remove_pet_shop_item("cap"))
        assert coord.pet_worn(kid)["hat"] == {"id": "top_hat"}


# ── hatching ────────────────────────────────────────────────────────────────


def _hatch(coord, storage, kid):
    pet = coord._pets()[kid.id]
    pet["egg_laid"] = True
    pet["stage_reached"] = "grown"
    with patch(f"{PETS}.now", return_value=_now()), patch(f"{PETS}.as_local", side_effect=lambda d: d):
        run(coord.async_adopt_pet(kid.id, "cat", "Mimi", hatch_egg=True))


class TestHatching:
    def test_carry_over_on_keeps_the_wardrobe(self):
        coord, storage, kid, _ = _setup()
        _buy(coord, kid.id, "cap")
        run(coord.async_equip_pet_item(kid.id, "cap", True))
        _hatch(coord, storage, kid)
        assert coord.pet_owned(kid.id) == ["cap"]
        assert coord.pet_worn(kid)["hat"]["id"] == "cap"

    def test_carry_over_off_resets_owned_items(self):
        coord, storage, kid, _ = _setup()
        storage.set_setting("pet_shop_carry_over", False)
        _buy(coord, kid.id, "cap")
        run(coord.async_equip_pet_item(kid.id, "cap", True))
        _hatch(coord, storage, kid)
        assert coord.pet_owned(kid.id) == []
        assert "hat" not in coord.pet_worn(kid)

    def test_renaming_never_resets(self):
        coord, storage, kid, _ = _setup()
        storage.set_setting("pet_shop_carry_over", False)
        _buy(coord, kid.id, "cap")
        with patch(f"{PETS}.now", return_value=_now()), patch(f"{PETS}.as_local", side_effect=lambda d: d):
            run(coord.async_adopt_pet(kid.id, "dragon", "Sparks"))
        assert coord.pet_owned(kid.id) == ["cap"]


# ── sensor shape ────────────────────────────────────────────────────────────


class TestSensor:
    def test_shop_off_and_untouched_wardrobe_adds_nothing(self):
        coord, _storage, kid, _ = _setup(shop=False, level=9)
        state = coord.pet_state(kid)
        assert "worn" not in state and "shop" not in state
        assert state["accessories"] == ["bow", "top_hat"]

    def test_shop_on_adds_compact_fields(self):
        coord, storage, kid, _ = _setup(points=200, level=9)
        storage.set_setting("pet_shop_approve_over", 50)
        _buy(coord, kid.id, "cap")
        _buy(coord, kid.id, "rainbow")
        run(coord.async_equip_pet_item(kid.id, "cap", True))
        state = coord.pet_state(storage.get_child(kid.id))
        assert state["worn"] == {"hat": {"id": "cap", "emoji": "🧢"}, "neck": {"id": "bow"}}
        assert state["shop"] == {"owned": ["cap"], "pending": ["rainbow"], "approve_over": 50}
        # The catalogue itself never rides on the sensor.
        assert "items" not in state["shop"]
        assert len(json.dumps(state)) < 1024

    def test_a_long_owned_list_stays_off_the_sensor(self):
        coord, storage, kid, _ = _setup()
        coord._pet_wardrobe(kid.id, create=True)["owned"] = [f"item{i}" for i in range(41)]
        assert "owned" not in coord.pet_state(kid)["shop"]

    def test_overview_children_carry_it(self):
        coord, storage, kid, _ = _setup()
        _buy(coord, kid.id, "cap")
        with patch.object(sensor_module, "dt_util", wraps=sensor_module.dt_util):
            coord.data = run(coord._async_update_data())
            common = sensor_module._compute_common(coord)
            summary = {c["id"]: c for c in sensor_module._build_children_summary(coord, common)}
        assert summary[kid.id]["pet"]["shop"]["owned"] == ["cap"]

    def test_card_catalogue_lists_shown_and_owned_items(self):
        coord, storage, kid, _ = _setup()
        coord._pet_wardrobe(kid.id, create=True)["owned"] = ["ghost_sheet"]
        view = coord.pet_shop_for_child(kid.id)
        ids = [i["id"] for i in view["items"]]
        assert "ghost_sheet" in ids and "cap" in ids
        assert view["enabled"] is True and view["spendable"] == 100
        assert next(i for i in view["items"] if i["id"] == "cap")["default"] is True


# ── auth: services and WebSocket ────────────────────────────────────────────


class TestServices:
    def _register(self):
        from custom_components.taskmate.family_services import async_register_family_services

        hass = MagicMock()
        registered = {}
        hass.services.async_register = lambda d, name, handler, schema=None: registered.setdefault(
            name, (handler, schema)
        )
        coord = MagicMock()
        coord.async_buy_pet_item = AsyncMock()
        coord.async_equip_pet_item = AsyncMock()
        gate = AsyncMock()
        async_register_family_services(
            hass,
            child_action=lambda h: h,
            parent_action=lambda h: h,
            get_coordinator=lambda: coord,
            require_linked_child=gate,
        )
        return registered, coord, gate

    def test_buy_goes_through_the_linked_child_gate(self):
        registered, coord, gate = self._register()
        handler, _schema = registered["buy_pet_item"]
        run(handler(MagicMock(data={"child_id": "malia", "item_id": "cap"})))
        assert gate.await_args.args[3] == "malia"
        coord.async_buy_pet_item.assert_awaited_once_with("malia", "cap")

    def test_a_refused_gate_stops_the_purchase(self):
        registered, coord, gate = self._register()
        gate.side_effect = PermissionError("nope")
        handler, _schema = registered["buy_pet_item"]
        with pytest.raises(PermissionError):
            run(handler(MagicMock(data={"child_id": "malia", "item_id": "cap"})))
        coord.async_buy_pet_item.assert_not_awaited()

    def test_equip_goes_through_the_gate(self):
        registered, coord, gate = self._register()
        handler, _schema = registered["equip_pet_item"]
        run(handler(MagicMock(data={"child_id": "malia", "item_id": "bow", "wear": False})))
        assert gate.await_args.args[3] == "malia"
        coord.async_equip_pet_item.assert_awaited_once_with("malia", "bow", False)


def _ws_setup(linked=""):
    coord, storage, kid, other = _setup()
    if linked:
        kid.linked_user_id = linked
        storage.update_child(kid)
    coord.hass.data = {DOMAIN: {"e": coord}}

    async def _get_user(uid):
        return SimpleNamespace(is_admin=uid == "admin")

    coord.hass.auth = MagicMock()
    coord.hass.auth.async_get_user = _get_user
    coord.async_record_audit = AsyncMock()
    return coord, storage, kid, other


def _conn(user_id, admin=False):
    connection = MagicMock()
    connection.user = SimpleNamespace(id=user_id, is_admin=admin, name=user_id)
    return connection


class TestWebSocket:
    def test_catalogue_follows_the_linked_child_rule(self):
        from custom_components.taskmate import websocket_pet_shop as ws

        coord, _storage, kid, _ = _ws_setup(linked="u-malia")
        own = _conn("u-malia")
        run(ws.ws_pet_shop_catalogue(coord.hass, own, {"id": 1, "type": ws.WS_PET_SHOP_CATALOGUE, "child_id": kid.id}))
        assert own.send_result.called
        stranger = _conn("u-vaiha")
        run(
            ws.ws_pet_shop_catalogue(
                coord.hass, stranger, {"id": 2, "type": ws.WS_PET_SHOP_CATALOGUE, "child_id": kid.id}
            )
        )
        assert stranger.send_error.called and not stranger.send_result.called

    def test_catalogue_edits_are_admin_only_and_audited(self):
        from custom_components.taskmate import websocket_pet_shop as ws

        coord, *_ = _ws_setup()
        msg = {
            "id": 3,
            "type": ws.WS_PET_SHOP_SAVE_ITEM,
            "name": "Party hat",
            "emoji": "🥳",
            "slot": "hat",
            "cost": 9,
            "level": 0,
            "shown": True,
            "tint": "",
        }
        child = _conn("u-kid")
        run(ws.ws_pet_shop_save_item(coord.hass, child, msg))
        assert child.send_error.called and len(coord.pet_shop_items()) == 7
        parent = _conn("admin", admin=True)
        run(ws.ws_pet_shop_save_item(coord.hass, parent, msg))
        assert parent.send_result.called and len(coord.pet_shop_items()) == 8
        coord.async_record_audit.assert_awaited()
        assert coord.async_record_audit.await_args.args[2] == "pet_shop/save_item"
        assert coord.async_record_audit.await_args.args[3] == "Party hat"

    def test_decide_is_admin_only(self):
        from custom_components.taskmate import websocket_pet_shop as ws

        coord, storage, kid, _ = _ws_setup()
        storage.set_setting("pet_shop_approve_over", 10)
        result = _buy(coord, kid.id, "cap")
        msg = {"id": 4, "type": ws.WS_PET_SHOP_DECIDE, "purchase_id": result["purchase_id"], "approve": True}
        child = _conn("u-kid")
        run(ws.ws_pet_shop_decide(coord.hass, child, msg))
        assert child.send_error.called and coord.pet_owned(kid.id) == []
        parent = _conn("admin", admin=True)
        with patch(SHOP, return_value=_now()):
            run(ws.ws_pet_shop_decide(coord.hass, parent, msg))
        assert coord.pet_owned(kid.id) == ["cap"]


def test_undo_refuses_a_pet_shop_purchase():
    coord, storage, kid, _ = _setup()
    txn = PointsTransaction(child_id=kid.id, points=-15, reason="Pet shop: Sunglasses", created_at=_now())
    storage.add_points_transaction(txn)
    with pytest.raises(ValueError, match="can't be undone"):
        run(coord.async_undo_transaction(txn.id))


def test_settings_are_accepted_by_the_settings_schema():
    from custom_components.taskmate.websocket import _SUBKEY_SETTINGS, _UPDATE_SETTINGS_SCHEMA

    keys = {getattr(k, "schema", k) for k in _UPDATE_SETTINGS_SCHEMA}
    for key in ("pet_shop_enabled", "pet_shop_approve_over", "pet_shop_carry_over"):
        assert key in keys and key in _SUBKEY_SETTINGS
