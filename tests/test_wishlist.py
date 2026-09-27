"""Wishlist with pledges (#932).

A child adds a wish, a parent approves it (optionally changing the target),
the child moves points in, relatives pledge through a parent, and a funded
wish becomes an ordinary reward claim. The money rules are the point of these
tests: saved points leave the balance and stay the child's; pledged points
never reach any balance; every movement is logged; declining or deleting a
wish gives the child their savings back and voids the pledges.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from datetime import timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
import yaml

from custom_components.taskmate import wishlist_services
from custom_components.taskmate.const import (
    WISH_KEEP_DECLINED_PER_CHILD,
    WISH_MAX_OPEN_PER_CHILD,
)
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Child,
    Reward,
    RewardClaim,
    Wish,
    WishPledge,
    clean_wish_link,
)
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
NOW = dt.datetime(2026, 9, 27, 10, 0, 0, tzinfo=UTC)
INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _storage(children, wishes=(), rewards=(), claims=()) -> TaskMateStorage:
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "children": [c.to_dict() for c in children],
        "rewards": [r.to_dict() for r in rewards],
        "reward_claims": [c.to_dict() for c in claims],
        "wishes": [w.to_dict() for w in wishes],
        "completions": [],
        "points_transactions": [],
    }
    return storage


def _kids(points=100):
    return [Child(name="Mia", id="mia", points=points), Child(name="Leo", id="leo", points=50)]


def _coord(children=None, wishes=(), rewards=(), claims=()):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.async_add_executor_job = AsyncMock()
    coord.storage = _storage(children or _kids(), wishes, rewards, claims)
    coord.async_refresh = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.badges = None
    return coord


def _wish(**kw) -> Wish:
    kw.setdefault("child_id", "mia")
    kw.setdefault("name", "Lego treehouse")
    kw.setdefault("target", 100)
    kw.setdefault("suggested_target", kw["target"])
    kw.setdefault("status", "active")
    kw.setdefault("id", "w1")
    return Wish(**kw)


def _points(coord, child_id="mia"):
    return coord.storage.get_child(child_id).points


def _txns(coord):
    return [(t.child_id, t.points, t.reason) for t in coord.storage.get_points_transactions()]


def _go(coro):
    with patch("custom_components.taskmate.coord_wishlist.dt_util.now", return_value=NOW):
        return run(coro)


# ── the model ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,<b>x</b>",
        "//evil.example",
        "/local/path",
        "ftp://example.com",
        "https://exa mple.com",
        "https://example.com/\x07",
        "https://" + "a" * 600 + ".com",
    ],
)
def test_links_that_are_not_plain_http_are_dropped(link):
    assert clean_wish_link(link) == ""


def test_http_and_https_links_are_kept():
    assert clean_wish_link(" https://www.lego.com/set?id=1 ") == "https://www.lego.com/set?id=1"
    assert clean_wish_link("http://shop.example/x") == "http://shop.example/x"


def test_wish_round_trips_and_sanitises_on_load():
    wish = _wish(saved=20, pledges=[WishPledge(name="Grandma", points=30, id="p1")], link="https://lego.com")
    loaded = Wish.from_dict(wish.to_dict())
    assert loaded.to_dict() == wish.to_dict()
    assert (loaded.pledged, loaded.remaining, loaded.funded) == (30, 50, False)

    tampered = wish.to_dict() | {"link": "javascript:alert(1)", "image_url": "https://evil/x.png", "status": "hacked"}
    bad = Wish.from_dict(tampered)
    assert (bad.link, bad.image_url, bad.status) == ("", "", "pending")


def test_signed_image_url_is_stored_bare():
    image = "/api/taskmate/image/" + "a" * 32 + ".jpg"
    assert Wish.from_dict({"image_url": image + "?authSig=abc"}).image_url == image


def test_ordinary_reward_claims_keep_their_shape():
    claim = RewardClaim(reward_id="r1", child_id="mia", claimed_at=NOW)
    assert "wish_id" not in claim.to_dict()
    wished = RewardClaim(reward_id="w1", child_id="mia", claimed_at=NOW, wish_id="w1")
    assert RewardClaim.from_dict(wished.to_dict()).wish_id == "w1"


# ── adding and approving ─────────────────────────────────────────────────────


def test_a_new_wish_waits_for_approval_and_tells_the_parents():
    coord = _coord()
    wish = _go(coord.async_add_wish("mia", "  Roller   skates ", 400, link="https://decathlon.co.uk"))
    stored = coord.storage.get_wish(wish.id)
    assert (stored.status, stored.name, stored.target, stored.suggested_target) == (
        "pending",
        "Roller skates",
        400,
        400,
    )
    assert stored.link == "https://decathlon.co.uk"
    assert coord.notifications.fire.await_args.args[0] == "wish_requested"


def test_a_bad_link_is_refused_not_silently_dropped():
    coord = _coord()
    with pytest.raises(ValueError, match="http"):
        _go(coord.async_add_wish("mia", "Skates", 40, link="javascript:alert(1)"))
    assert coord.storage.get_wishes() == []


@pytest.mark.parametrize("target", [0, -5, 100001, "lots"])
def test_the_target_must_be_sensible(target):
    with pytest.raises(ValueError):
        _go(_coord().async_add_wish("mia", "Skates", target))


def test_a_child_can_have_only_so_many_wishes_on_the_go():
    wishes = [_wish(id=f"w{i}", status="active") for i in range(WISH_MAX_OPEN_PER_CHILD)]
    coord = _coord(wishes=wishes)
    with pytest.raises(ValueError, match="wishes on the go"):
        _go(coord.async_add_wish("mia", "One more", 10))
    # A sibling's slots are their own.
    _go(coord.async_add_wish("leo", "Football", 10))


def test_declined_and_redeemed_wishes_do_not_hold_a_slot():
    wishes = [_wish(id=f"w{i}", status="declined" if i % 2 else "redeemed") for i in range(WISH_MAX_OPEN_PER_CHILD)]
    _go(_coord(wishes=wishes).async_add_wish("mia", "One more", 10))


def test_approving_can_change_the_target():
    coord = _coord(wishes=[_wish(status="pending", target=900)])
    _go(coord.async_approve_wish("w1", target=750))
    wish = coord.storage.get_wish("w1")
    assert (wish.status, wish.target, wish.approved_at) == ("active", 750, NOW)


def test_only_a_waiting_wish_can_be_approved():
    with pytest.raises(ValueError):
        _go(_coord(wishes=[_wish(status="active")]).async_approve_wish("w1"))


def test_a_child_can_withdraw_a_waiting_wish_but_not_an_active_one():
    coord = _coord(wishes=[_wish(id="w1", status="pending"), _wish(id="w2", status="active")])
    _go(coord.async_withdraw_wish("w1", "mia"))
    assert coord.storage.get_wish("w1") is None
    with pytest.raises(ValueError):
        _go(coord.async_withdraw_wish("w2", "mia"))


# ── moving points in and out ─────────────────────────────────────────────────


def test_moving_points_reserves_them_out_of_the_balance():
    coord = _coord(wishes=[_wish()])
    moved = _go(coord.async_move_points_to_wish("w1", "mia", 30))
    assert moved == 30
    assert _points(coord) == 70
    assert coord.storage.get_wish("w1").saved == 30
    assert _txns(coord) == [("mia", -30, "Wish savings: Lego treehouse")]


def test_moving_is_capped_at_what_the_wish_still_needs_and_the_balance():
    coord = _coord(wishes=[_wish(target=100, saved=50, pledges=[WishPledge(name="Gran", points=40)])])
    assert _go(coord.async_move_points_to_wish("w1", "mia", 60)) == 10
    coord = _coord(children=_kids(points=15), wishes=[_wish()])
    assert _go(coord.async_move_points_to_wish("w1", "mia", 60)) == 15
    assert _points(coord) == 0


def test_points_promised_to_a_pending_claim_cannot_be_moved():
    reward = Reward(name="Film", cost=90, id="r1")
    claim = RewardClaim(reward_id="r1", child_id="mia", claimed_at=NOW)
    coord = _coord(wishes=[_wish()], rewards=[reward], claims=[claim])
    assert _go(coord.async_move_points_to_wish("w1", "mia", 50)) == 10


def test_a_child_cannot_save_into_a_siblings_wish():
    coord = _coord(wishes=[_wish(child_id="leo")])
    with pytest.raises(ValueError, match="not found"):
        _go(coord.async_move_points_to_wish("w1", "mia", 10))


def test_saving_needs_an_approved_wish():
    with pytest.raises(ValueError):
        _go(_coord(wishes=[_wish(status="pending")]).async_move_points_to_wish("w1", "mia", 10))


def test_taking_points_back_returns_only_the_childs_own_savings():
    coord = _coord(wishes=[_wish(saved=30, pledges=[WishPledge(name="Gran", points=40)])])
    assert _go(coord.async_take_points_from_wish("w1", "mia", 100)) == 30
    wish = coord.storage.get_wish("w1")
    assert (wish.saved, wish.pledged) == (0, 40)
    assert _points(coord) == 130
    assert _txns(coord) == [("mia", 30, "Wish savings taken back: Lego treehouse")]


def test_moving_in_and_out_does_not_farm_leaderboard_points():
    coord = _coord(wishes=[_wish()])
    for _ in range(3):
        _go(coord.async_move_points_to_wish("w1", "mia", 50))
        _go(coord.async_take_points_from_wish("w1", "mia", 50))
    assert coord.storage.get_season_points(NOW.strftime("%Y-%m")) == {}
    assert _points(coord) == 100


# ── pledges ──────────────────────────────────────────────────────────────────


def test_a_pledge_never_touches_the_childs_balance_and_is_logged():
    coord = _coord(wishes=[_wish(saved=20)])
    pledge = _go(coord.async_pledge_to_wish("w1", "Grandma", 25, "Well done!"))
    assert _points(coord) == 100
    wish = coord.storage.get_wish("w1")
    assert (wish.pledged, wish.pledges[0].name, wish.pledges[0].message) == (25, "Grandma", "Well done!")
    assert _txns(coord) == [("mia", 0, "Wish pledge from Grandma (+25): Lego treehouse")]
    assert pledge.created_at == NOW


def test_a_pledge_is_capped_at_the_remaining_target():
    coord = _coord(wishes=[_wish(saved=90)])
    assert _go(coord.async_pledge_to_wish("w1", "Grandad", 50)).points == 10
    with pytest.raises(ValueError, match="fully funded"):
        _go(coord.async_pledge_to_wish("w1", "Grandad", 5))


def test_only_the_child_is_told_about_a_pledge():
    coord = _coord(wishes=[_wish()])
    _go(coord.async_pledge_to_wish("w1", "Uncle Rob", 10))
    call = coord.notifications.fire.await_args
    assert call.args[0] == "wish_pledged"
    assert call.args[1]["pledger"] == "Uncle Rob"
    assert call.kwargs["only_recipients"] == {"child:mia"}


def test_removing_a_pledge_is_logged():
    coord = _coord(wishes=[_wish(pledges=[WishPledge(name="Gran", points=40, id="p1")])])
    _go(coord.async_remove_wish_pledge("w1", "p1"))
    assert coord.storage.get_wish("w1").pledges == []
    assert _txns(coord) == [("mia", 0, "Wish pledge removed (Gran, 40): Lego treehouse")]


# ── redeeming ────────────────────────────────────────────────────────────────


def _funded(**kw):
    return _wish(saved=60, pledges=[WishPledge(name="Gran", points=40, id="p1")], **kw)


def test_a_funded_wish_becomes_an_ordinary_pending_claim():
    coord = _coord(wishes=[_funded()])
    claim = _go(coord.async_request_wish_redeem("w1", "mia"))
    assert (claim.wish_id, claim.reward_id, claim.approved) == ("w1", "w1", False)
    assert coord.storage.get_pending_reward_claims()[0].id == claim.id
    wish = coord.storage.get_wish("w1")
    assert (wish.status, wish.claim_id) == ("redeem_requested", claim.id)
    assert coord.notifications.fire.await_args.args[0] == "pending_reward_claim"
    # The claim was paid for already: nothing is committed against the wallet.
    assert coord.is_pool_mode_claim(claim) is True


def test_an_unfunded_wish_cannot_be_redeemed():
    with pytest.raises(ValueError, match="more points"):
        _go(_coord(wishes=[_wish(saved=10)]).async_request_wish_redeem("w1", "mia"))


def test_approving_the_claim_spends_the_wish_not_the_wallet():
    coord = _coord(wishes=[_funded()])
    claim = _go(coord.async_request_wish_redeem("w1", "mia"))
    _go(coord.async_approve_reward(claim.id))
    assert _points(coord) == 100
    wish = coord.storage.get_wish("w1")
    assert (wish.status, wish.redeemed_at) == ("redeemed", NOW)
    stored = coord.storage.get_reward_claims()[0]
    assert (stored.approved, stored.approved_cost) == (True, 60)
    assert ("mia", 0, "Wish redeemed: Lego treehouse") in _txns(coord)
    coord.notifications.clear_approval.assert_awaited_with("pending_reward_claim", claim.id)


def test_rejecting_the_claim_puts_the_wish_back_to_saving():
    coord = _coord(wishes=[_funded()])
    claim = _go(coord.async_request_wish_redeem("w1", "mia"))
    _go(coord.async_reject_reward(claim.id))
    wish = coord.storage.get_wish("w1")
    assert (wish.status, wish.claim_id, wish.saved, wish.pledged) == ("active", "", 60, 40)
    assert coord.storage.get_reward_claims() == []


def test_removing_a_pledge_from_a_waiting_redemption_withdraws_the_claim():
    coord = _coord(wishes=[_funded()])
    claim = _go(coord.async_request_wish_redeem("w1", "mia"))
    _go(coord.async_remove_wish_pledge("w1", "p1"))
    assert coord.storage.get_wish("w1").status == "active"
    assert coord.storage.get_reward_claims() == []
    coord.notifications.clear_approval.assert_awaited_with("pending_reward_claim", claim.id)


def test_no_saving_or_taking_back_while_a_redemption_is_waiting():
    coord = _coord(wishes=[_funded(status="redeem_requested")])
    with pytest.raises(ValueError):
        _go(coord.async_take_points_from_wish("w1", "mia", 10))


# ── declining and deleting ───────────────────────────────────────────────────


def test_declining_returns_savings_and_voids_pledges():
    coord = _coord(wishes=[_wish(saved=30, pledges=[WishPledge(name="Gran", points=20)])])
    _go(coord.async_decline_wish("w1", "Too pricey this year"))
    wish = coord.storage.get_wish("w1")
    assert (wish.status, wish.saved, wish.pledges, wish.decline_reason) == ("declined", 0, [], "Too pricey this year")
    assert _points(coord) == 130  # the pledged 20 never reach the child
    assert _txns(coord) == [
        ("mia", 30, "Wish refund (declined): Lego treehouse"),
        ("mia", 0, "Wish pledge voided (Gran, 20): Lego treehouse"),
    ]
    assert coord.storage.get_season_points(NOW.strftime("%Y-%m")) == {}


def test_declining_a_waiting_redemption_cancels_its_claim():
    coord = _coord(wishes=[_funded()])
    claim = _go(coord.async_request_wish_redeem("w1", "mia"))
    _go(coord.async_decline_wish("w1"))
    assert coord.storage.get_reward_claims() == []
    assert _points(coord) == 160
    coord.notifications.clear_approval.assert_awaited_with("pending_reward_claim", claim.id)


def test_only_a_few_declined_wishes_are_kept():
    old = [
        _wish(id=f"d{i}", status="declined", declined_at=NOW - dt.timedelta(days=i + 1))
        for i in range(WISH_KEEP_DECLINED_PER_CHILD)
    ]
    coord = _coord(wishes=[*old, _wish(id="new", status="pending")])
    _go(coord.async_decline_wish("new"))
    kept = {w.id for w in coord.storage.get_wishes()}
    assert "new" in kept
    assert f"d{WISH_KEEP_DECLINED_PER_CHILD - 1}" not in kept
    assert len(kept) == WISH_KEEP_DECLINED_PER_CHILD


def test_removing_a_wish_refunds_and_deletes_its_picture():
    image = "/api/taskmate/image/" + "b" * 32 + ".png"
    coord = _coord(wishes=[_wish(saved=45, image_url=image)])
    with patch("custom_components.taskmate.coord_wishlist.images.async_delete_image", AsyncMock()) as delete:
        _go(coord.async_remove_wish("w1"))
    assert coord.storage.get_wish("w1") is None
    assert _points(coord) == 145
    delete.assert_awaited_once_with(coord.hass, image)


def test_deleting_a_child_takes_their_wishes_with_them():
    coord = _coord(wishes=[_wish(), _wish(id="w2", child_id="leo")])
    run(coord._async_remove_wishes_for_child("mia"))
    assert [w.id for w in coord.storage.get_wishes()] == ["w2"]


def test_wish_rows_cannot_be_undone_one_at_a_time():
    coord = _coord(wishes=[_wish()])
    _go(coord.async_move_points_to_wish("w1", "mia", 10))
    txn = coord.storage.get_points_transactions()[0]
    with pytest.raises(ValueError, match="can't be undone"):
        run(coord.async_undo_transaction(txn.id))


# ── pictures ─────────────────────────────────────────────────────────────────

PHOTO = "/api/taskmate/photo/" + "c" * 32 + ".jpg"


def test_a_fresh_upload_becomes_the_wish_picture():
    coord = _coord()
    image = "/api/taskmate/image/" + "d" * 32 + ".jpg"
    with patch("custom_components.taskmate.coord_wishlist.images.async_adopt_photo", AsyncMock(return_value=image)):
        wish = _go(coord.async_add_wish("mia", "Skates", 40, photo_url=PHOTO))
    assert coord.storage.get_wish(wish.id).image_url == image


@pytest.mark.parametrize("photo", ["https://evil.example/x.jpg", "/api/taskmate/image/" + "e" * 32 + ".jpg"])
def test_only_our_own_photo_uploads_are_accepted(photo):
    with pytest.raises(ValueError, match="picture"):
        _go(_coord().async_add_wish("mia", "Skates", 40, photo_url=photo))


def test_someones_chore_evidence_cannot_become_a_wish_picture():
    coord = _coord()
    coord.storage._data["completions"] = [{"id": "c1", "chore_id": "x", "child_id": "leo", "photo_url": PHOTO}]
    adopt = AsyncMock(return_value="/api/taskmate/image/" + "d" * 32 + ".jpg")
    with patch("custom_components.taskmate.coord_wishlist.images.async_adopt_photo", adopt):
        with pytest.raises(ValueError, match="picture"):
            _go(coord.async_add_wish("mia", "Skates", 40, photo_url=PHOTO))
    adopt.assert_not_awaited()


def test_adopt_photo_copies_a_recent_image_and_refuses_heic(tmp_path):
    from custom_components.taskmate import images, photos

    hass = MagicMock()
    hass.config.path = lambda sub: str(tmp_path / sub)

    async def executor(fn, *args):
        return fn(*args)

    hass.async_add_executor_job = executor
    (tmp_path / photos.PHOTOS_DIR).mkdir()
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    (tmp_path / photos.PHOTOS_DIR / ("c" * 32 + ".jpg")).write_bytes(jpeg)
    url = run(images.async_adopt_photo(hass, PHOTO))
    assert url and images.is_taskmate_image_url(url)
    assert (tmp_path / images.IMAGES_DIR / url.rsplit("/", 1)[1]).read_bytes() == jpeg
    assert not (tmp_path / photos.PHOTOS_DIR / ("c" * 32 + ".jpg")).exists()

    heic = "/api/taskmate/photo/" + "f" * 32 + ".heic"
    (tmp_path / photos.PHOTOS_DIR / ("f" * 32 + ".heic")).write_bytes(b"\x00\x00\x00\x18ftypheic" + b"0" * 50)
    assert run(images.async_adopt_photo(hass, heic)) is None


# ── what the card and the panel see ──────────────────────────────────────────


def test_sensor_rows_are_compact_and_skip_the_history():
    image = "/api/taskmate/image/" + "a" * 32 + ".jpg"
    wishes = [
        _wish(id="plain"),
        _wish(
            id="full",
            saved=10,
            link="https://lego.com",
            image_url=image,
            pledges=[
                WishPledge(name="Gran", points=5),
                WishPledge(name="Rob", points=20),
                WishPledge(name="Gran", points=30),
            ],
        ),
        _wish(id="no", status="declined", decline_reason="Not now"),
        _wish(id="done", status="redeemed"),
    ]
    wishes.append(_wish(id="sibling", child_id="leo"))
    rows = {r["id"]: r for r in _coord(wishes=wishes).wishlist_sensor_rows("mia")}
    assert set(rows) == {"plain", "full", "no"}
    assert rows["plain"] == {"id": "plain", "name": "Lego treehouse", "target": 100, "status": "active"}
    assert rows["full"]["pledges"] == [{"name": "Gran", "points": 35}, {"name": "Rob", "points": 20}]
    assert (rows["full"]["pledged"], rows["full"]["image_url"], rows["full"]["link"]) == (55, image, "https://lego.com")
    assert rows["no"]["decline_reason"] == "Not now"


def test_a_childs_wishlist_attribute_stays_under_the_recorder_limit():
    """Worst case for one child: every slot used, long everything, many pledgers."""
    from custom_components.taskmate.sensor import ChildWishlistSensor

    image = "/api/taskmate/image/" + "a" * 32 + ".jpg"
    wishes = [
        _wish(
            id=f"{i}-" + "x" * 14,
            name="N" * 60,
            target=100000,
            saved=12345,
            link="https://example.com/" + "p" * 480,
            image_url=image,
            pledges=[WishPledge(name=f"{'R' * 36} {p}", points=100) for p in range(50)],
        )
        for i in range(WISH_MAX_OPEN_PER_CHILD)
    ]
    wishes += [
        _wish(id=f"d{i}", status="declined", decline_reason="R" * 200) for i in range(WISH_KEEP_DECLINED_PER_CHILD)
    ]
    sensor = ChildWishlistSensor.__new__(ChildWishlistSensor)
    sensor.coordinator = _coord(wishes=wishes)
    sensor.child_id = "mia"
    attrs = sensor.extra_state_attributes
    assert attrs["wishlist_child_id"] == "mia"
    assert len(attrs["wishes"]) == WISH_MAX_OPEN_PER_CHILD + WISH_KEEP_DECLINED_PER_CHILD
    size = len(json.dumps(attrs))
    assert size < 16384, size
    assert sensor.native_value == WISH_MAX_OPEN_PER_CHILD


def test_pending_wish_claims_show_up_in_the_approval_lists():
    from custom_components.taskmate import sensor as sensor_module

    wish = _funded(status="redeem_requested", claim_id="c1")
    claim = RewardClaim(reward_id="w1", child_id="mia", claimed_at=NOW, wish_id="w1", id="c1")
    coord = _coord(wishes=[wish], claims=[claim])
    common = {
        "reward_lookup": {},
        "wish_lookup": {w.id: w for w in coord.storage.get_wishes()},
        "child_lookup": {c.id: c for c in coord.storage.get_children()},
        "pending_reward_claim_objs": [claim],
    }
    rows = sensor_module._build_pending_reward_claims(common)
    assert (rows[0]["reward_name"], rows[0]["cost"], rows[0]["reward_icon"]) == ("Lego treehouse", 100, "mdi:heart")


def test_panel_state_carries_full_pledges_and_signed_images():
    image = "/api/taskmate/image/" + "a" * 32 + ".jpg"
    coord = _coord(wishes=[_wish(image_url=image, pledges=[WishPledge(name="Gran", points=5, message="Hi")])])
    with patch("custom_components.taskmate.coord_wishlist.images.sign_image_url", lambda hass, u: u + "?authSig=x"):
        row = coord.wishlist_state()[0]
    assert row["image_url"].endswith("?authSig=x")
    assert row["pledges"][0]["message"] == "Hi"
    assert (row["pledged"], row["remaining"], row["funded"]) == (5, 95, False)


def test_a_restored_backup_is_sanitised():
    storage = _storage(_kids())
    storage.import_data(
        {"wishes": [{"id": "w", "child_id": "mia", "name": "x", "target": 5, "link": "javascript:alert(1)"}, "junk"]}
    )
    assert storage.get_wishes()[0].link == ""
    assert len(storage._data["wishes"]) == 1


# ── services ─────────────────────────────────────────────────────────────────


def _registered(monkeypatch):
    # conftest stubs config_validation wholesale; the real cv.string is a str coercion.
    monkeypatch.setattr(wishlist_services, "cv", MagicMock(string=str))
    hass = MagicMock()
    registered = {}
    hass.services.async_register = lambda domain, name, handler, schema: registered.__setitem__(name, (handler, schema))
    coordinator = MagicMock()
    for attr in dir(TaskMateCoordinator):
        if attr.startswith("async_") and "wish" in attr:
            setattr(coordinator, attr, AsyncMock())
    linked = AsyncMock()
    marks = {"child": [], "parent": []}

    def child_action(handler):
        marks["child"].append(handler)
        return handler

    def parent_action(handler):
        marks["parent"].append(handler)
        return handler

    wishlist_services.async_register_wishlist_services(
        hass,
        child_action=child_action,
        parent_action=parent_action,
        get_coordinator=lambda: coordinator,
        require_linked_child=linked,
    )
    return registered, coordinator, linked, marks


CHILD_SERVICES = {"add_wish", "withdraw_wish", "move_points_to_wish", "take_points_from_wish", "request_wish_redeem"}
PARENT_SERVICES = {"approve_wish", "decline_wish", "pledge_to_wish", "remove_wish_pledge", "remove_wish"}


def test_every_wishlist_service_is_registered_and_declared(monkeypatch):
    registered, *_ = _registered(monkeypatch)
    assert set(registered) == CHILD_SERVICES | PARENT_SERVICES == set(wishlist_services.WISHLIST_SERVICES)
    declared = yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))["services"]
    for name in registered:
        assert name in declared and name in strings
        assert set(declared[name]["fields"]) == set(strings[name]["fields"])


def test_child_services_go_through_the_linked_child_gate(monkeypatch):
    registered, coordinator, linked, marks = _registered(monkeypatch)
    assert len(marks["child"]) == len(CHILD_SERVICES) and len(marks["parent"]) == len(PARENT_SERVICES)
    handler, schema = registered["move_points_to_wish"]
    call = MagicMock()
    call.data = vol.Schema(schema)({"wish_id": "w1", "child_id": "mia", "points": "5"})
    run(handler(call))
    linked.assert_awaited_once()
    assert linked.await_args.args[3] == "mia"
    coordinator.async_move_points_to_wish.assert_awaited_once_with("w1", "mia", 5)


def test_parent_services_skip_the_child_gate(monkeypatch):
    registered, coordinator, linked, _ = _registered(monkeypatch)
    handler, schema = registered["pledge_to_wish"]
    call = MagicMock()
    call.data = vol.Schema(schema)({"wish_id": "w1", "name": "Grandma", "points": 20})
    run(handler(call))
    linked.assert_not_awaited()
    coordinator.async_pledge_to_wish.assert_awaited_once_with("w1", "Grandma", 20, "")


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        ("add_wish", {"child_id": "mia", "name": "", "target": 5}),
        ("add_wish", {"child_id": "mia", "name": "x", "target": 0}),
        ("pledge_to_wish", {"wish_id": "w1", "name": "Gran", "points": -1}),
        ("pledge_to_wish", {"wish_id": "w1", "name": "G" * 41, "points": 1}),
        ("move_points_to_wish", {"wish_id": "w1", "child_id": "mia", "points": 0}),
    ],
)
def test_service_schemas_refuse_bad_input(service, payload, monkeypatch):
    registered, *_ = _registered(monkeypatch)
    with pytest.raises(vol.Invalid):
        vol.Schema(registered[service][1])(payload)
