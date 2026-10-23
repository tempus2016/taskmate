"""Reward extras: per-child limits, gifts between children, ratings, the savings
forecast, reward pictures and printable vouchers."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import voucher
from custom_components.taskmate.models import ChoreCompletion, PointsTransaction, Reward, RewardClaim

from .test_completion_eligibility import _make_system, _now, run

EXTRAS = "custom_components.taskmate.coord_reward_extras.dt_util.now"
REWARDS = "custom_components.taskmate.coord_rewards.dt_util.now"
FUL = "custom_components.taskmate.coord_fulfilment.dt_util.now"
ST = "custom_components.taskmate.coord_screen_time.dt_util.now"


def _system(gifting=False, fulfilment=False):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.badges = None
    coord.async_start_unlock = AsyncMock()
    storage.set_setting("reward_gifting_enabled", gifting)
    storage.set_setting("reward_fulfilment_enabled", fulfilment)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        vaiha = run(coord.async_add_child("Vaiha"))
        malia = run(coord.async_add_child("Malia"))
    for kid in (vaiha, malia):
        kid.points = 500
        storage.update_child(kid)
    return coord, storage, mod, vaiha, malia


def _at(when):
    """Patch every clock the claim / approve / hand-over path reads."""
    from contextlib import ExitStack

    stack = ExitStack()
    for target in (EXTRAS, REWARDS, FUL, ST, "custom_components.taskmate.coordinator.dt_util.now"):
        stack.enter_context(patch(target, return_value=when))
    return stack


def _claim(coord, reward, kid, when=None, recipient=""):
    with _at(when or _now()):
        return run(coord.async_claim_reward(reward.id, kid.id, recipient))


def _approve(coord, claim, when=None):
    with _at(when or _now()):
        run(coord.async_approve_reward(claim.id))


def _stored(storage, claim_id):
    return next(c for c in storage.get_reward_claims() if c.id == claim_id)


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


# ── 17: per-child limit ──────────────────────────────────────────────────


class TestLimit:
    def _movie(self, storage, count=1, period="week"):
        reward = Reward(name="Pick the movie", cost=10, limit_count=count, limit_period=period)
        storage.add_reward(reward)
        return reward

    def test_once_a_week_each_counts_pending_and_approved(self):
        coord, storage, _mod, vaiha, malia = _system()
        movie = self._movie(storage)
        first = _claim(coord, movie, vaiha)  # Wednesday 2024-03-20
        _approve(coord, first)
        with pytest.raises(ValueError, match="once a week.*2024-03-25"):
            _claim(coord, movie, vaiha, _now(day=22))
        # The limit is per child: Malia still can.
        _claim(coord, movie, malia, _now(day=22))
        # Next Monday it opens again.
        _claim(coord, movie, vaiha, _now(day=25))

    def test_a_pending_claim_counts_and_a_rejected_one_does_not(self):
        coord, storage, _mod, vaiha, _malia = _system()
        movie = self._movie(storage, count=2, period="day")
        c1 = _claim(coord, movie, vaiha)
        with _at(_now()):
            run(coord.async_reject_reward(c1.id))
        c2 = _claim(coord, movie, vaiha)
        _approve(coord, c2)
        _claim(coord, movie, vaiha)
        with pytest.raises(ValueError, match="2 times a day"):
            _claim(coord, movie, vaiha, _now(hour=13))

    def test_month_window_and_no_limit(self):
        from custom_components.taskmate.coord_reward_extras import reward_limit_window

        assert reward_limit_window("month", dt.date(2024, 12, 15)) == (dt.date(2024, 12, 1), dt.date(2025, 1, 1))
        assert reward_limit_window("week", dt.date(2024, 3, 20)) == (dt.date(2024, 3, 18), dt.date(2024, 3, 25))
        coord, storage, _mod, vaiha, _malia = _system()
        free = Reward(name="Hug", cost=0)
        storage.add_reward(free)
        assert coord.reward_limit_next(free, vaiha.id) is None

    def test_the_rewards_sensor_carries_the_limit_only_when_set(self):
        coord, storage, _mod, vaiha, _malia = _system()
        movie = self._movie(storage)
        plain = Reward(name="Sweets", cost=5)
        storage.add_reward(plain)
        _claim(coord, movie, vaiha)
        coord.data = coord._build_data_snapshot()
        with _at(_now()), patch("custom_components.taskmate.sensor.dt_util.now", return_value=_now()):
            rows = {
                r["name"]: r for r in sensor_module._build_rewards_list(sensor_module._compute_common(coord), coord)
            }
        assert rows["Pick the movie"]["limit"] == {"count": 1, "period": "week"}
        assert rows["Pick the movie"]["limit_reached"] == {vaiha.id: "2024-03-25"}
        assert "limit" not in rows["Sweets"] and "limit_reached" not in rows["Sweets"]

    def test_limit_round_trips_and_bad_values_are_cleaned(self):
        r = Reward.from_dict({"name": "x", "limit_count": 500, "limit_period": "fortnight"})
        assert r.limit_count == 99 and r.limit_period == "week"
        assert Reward.from_dict(Reward(name="y", limit_count=2, limit_period="day").to_dict()).limit_period == "day"


# ── 29: gifts between children ───────────────────────────────────────────


class TestGifts:
    def test_switched_off_by_default(self):
        coord, storage, _mod, vaiha, malia = _system()
        reward = Reward(name="Ice cream", cost=60)
        storage.add_reward(reward)
        with pytest.raises(ValueError, match="switched off"):
            _claim(coord, reward, vaiha, recipient=malia.id)

    def test_the_buyer_pays_and_the_recipient_gets_it(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True, fulfilment=True)
        reward = Reward(name="Ice cream", cost=60)
        storage.add_reward(reward)
        claim = _claim(coord, reward, vaiha, recipient=malia.id)
        assert claim.child_id == vaiha.id and claim.recipient_id == malia.id
        assert _fired(coord, "taskmate_reward_claimed")[0]["recipient_id"] == malia.id
        with _at(_now()):
            assert coord.incoming_gifts(malia.id) == [
                {"claim_id": claim.id, "reward_name": "Ice cream", "reward_icon": "mdi:gift", "from_name": "Vaiha"}
            ]
            assert coord.incoming_gifts(vaiha.id) == []
        _approve(coord, claim)
        assert storage.get_child(vaiha.id).points == 440
        assert storage.get_child(malia.id).points == 500
        with _at(_now()):
            (owed,) = coord.owed_rewards()
            assert owed["child_id"] == malia.id and owed["from_name"] == "Vaiha"
            assert coord.owed_rewards(vaiha.id) == []
            # Only the recipient can say "Got it!".
            with pytest.raises(ValueError):
                run(coord.async_mark_reward_delivered(claim.id, by="child", child_id=vaiha.id))
            run(coord.async_mark_reward_delivered(claim.id, by="child", child_id=malia.id))

    def test_screen_minutes_go_to_the_recipient(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True)
        storage.set_setting("screen_time_enabled", True)
        reward = Reward(name="30 min Xbox", cost=40, screen_minutes=30)
        storage.add_reward(reward)
        _approve(coord, _claim(coord, reward, vaiha, recipient=malia.id))
        assert coord.screen_time_balance(malia.id) == 30
        assert coord.screen_time_balance(vaiha.id) == 0

    def test_recipient_must_be_eligible(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True)
        with _at(_now()):
            dad = run(coord.async_add_child("Dad"))
        dad.is_adult = True
        storage.update_child(dad)
        only_vaiha = Reward(name="Lego", cost=10, assigned_to=[vaiha.id])
        jackpot = Reward(name="Zoo", cost=10, is_jackpot=True)
        freeze = Reward(name="Freeze", cost=10, streak_freeze=True)
        plain = Reward(name="Sweets", cost=10)
        for r in (only_vaiha, jackpot, freeze, plain):
            storage.add_reward(r)
        with pytest.raises(ValueError, match="not available to Malia"):
            _claim(coord, only_vaiha, vaiha, recipient=malia.id)
        with pytest.raises(ValueError, match="only be bought for children"):
            _claim(coord, plain, vaiha, recipient=dad.id)
        with pytest.raises(ValueError, match="not found"):
            _claim(coord, plain, vaiha, recipient="nobody")
        for r in (jackpot, freeze):
            with pytest.raises(ValueError, match="can't be bought for someone else"):
                _claim(coord, r, vaiha, recipient=malia.id)
        # A sibling-only reward can still be bought FOR that sibling by someone else.
        only_malia = Reward(name="Doll", cost=10, assigned_to=[malia.id])
        storage.add_reward(only_malia)
        _claim(coord, only_malia, vaiha, recipient=malia.id)

    def test_a_waiting_gift_blocks_a_second_claim_for_the_same_child(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True)
        reward = Reward(name="Ice cream", cost=60)
        storage.add_reward(reward)
        _claim(coord, reward, vaiha, recipient=malia.id)
        with pytest.raises(ValueError, match="already waiting"):
            _claim(coord, reward, malia)
        # Vaiha may still get one for herself.
        _claim(coord, reward, vaiha)

    def test_the_limit_counts_against_the_recipient(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True)
        reward = Reward(name="Pick the movie", cost=10, limit_count=1, limit_period="week")
        storage.add_reward(reward)
        _approve(coord, _claim(coord, reward, vaiha, recipient=malia.id))
        with pytest.raises(ValueError, match="Malia can have"):
            _claim(coord, reward, malia)
        _claim(coord, reward, vaiha)

    def test_pending_claim_rows_name_the_recipient(self):
        coord, storage, _mod, vaiha, malia = _system(gifting=True)
        reward = Reward(name="Ice cream", cost=60)
        storage.add_reward(reward)
        _claim(coord, reward, vaiha, recipient=malia.id)
        _claim(coord, reward, vaiha)
        coord.data = coord._build_data_snapshot()
        rows = sensor_module._build_pending_reward_claims(sensor_module._compute_common(coord))
        gift = [r for r in rows if "recipient_id" in r]
        assert len(gift) == 1 and gift[0]["recipient_name"] == "Malia"


def test_removing_the_recipient_drops_their_waiting_gifts_only():
    coord, storage, _mod, vaiha, malia = _system(gifting=True)
    reward = Reward(name="Ice cream", cost=60)
    storage.add_reward(reward)
    waiting = _claim(coord, reward, vaiha, recipient=malia.id)
    given = _claim(coord, reward, vaiha)
    storage.remove_reward_claims_for_child(malia.id)
    ids = {c.id for c in storage.get_reward_claims()}
    assert waiting.id not in ids and given.id in ids


def test_claim_shape_is_unchanged_without_the_new_fields():
    claim = RewardClaim(reward_id="r", child_id="c", claimed_at=_now())
    out = claim.to_dict()
    assert "recipient_id" not in out and "rating" not in out
    back = RewardClaim.from_dict({**out, "recipient_id": "m", "rating": 7})
    assert back.recipient_id == "m" and back.holder_id == "m" and back.rating == 0


# ── 21: rate the reward ──────────────────────────────────────────────────


class TestRatings:
    def test_rate_after_approval_when_fulfilment_is_off(self):
        coord, storage, _mod, vaiha, _malia = _system()
        reward = Reward(name="Cinema trip", cost=50)
        storage.add_reward(reward)
        claim = _claim(coord, reward, vaiha)
        with _at(_now()):
            assert coord.rewards_to_rate(vaiha.id) == []  # still pending
        _approve(coord, claim)
        with _at(_now()):
            (item,) = coord.rewards_to_rate(vaiha.id)
            assert item == {"claim_id": claim.id, "reward_name": "Cinema trip", "reward_icon": "mdi:gift"}
            run(coord.async_rate_reward(claim.id, vaiha.id, 3))
            assert coord.rewards_to_rate(vaiha.id) == []
            with pytest.raises(ValueError, match="already been rated"):
                run(coord.async_rate_reward(claim.id, vaiha.id, 2))
        assert _stored(storage, claim.id).rating == 3
        assert _fired(coord, "taskmate_reward_rated")[0]["rating"] == 3

    def test_with_fulfilment_on_only_after_hand_over_and_only_for_three_days(self):
        coord, storage, _mod, vaiha, malia = _system(fulfilment=True)
        reward = Reward(name="Cinema trip", cost=50)
        storage.add_reward(reward)
        claim = _claim(coord, reward, vaiha)
        _approve(coord, claim)
        with _at(_now()):
            assert coord.rewards_to_rate(vaiha.id) == []
            with pytest.raises(ValueError, match="can't be rated yet"):
                run(coord.async_rate_reward(claim.id, vaiha.id, 2))
            run(coord.async_mark_reward_delivered(claim.id))
            assert len(coord.rewards_to_rate(vaiha.id)) == 1
            with pytest.raises(ValueError, match="Only the child"):
                run(coord.async_rate_reward(claim.id, malia.id, 2))
        with _at(_now() + dt.timedelta(days=4)):
            assert coord.rewards_to_rate(vaiha.id) == []

    def test_stars_must_be_one_to_three(self):
        coord, *_ = _system()
        with pytest.raises(ValueError, match="1 to 3"):
            run(coord.async_rate_reward("x", "y", 4))


# ── 25: savings forecast ─────────────────────────────────────────────────


def test_earn_rate_averages_the_last_fortnight_without_refunds():
    coord, storage, _mod, vaiha, malia = _system()
    now = _now()
    for days_ago, pts in ((1, 100), (13, 180), (20, 999)):
        storage.add_completion(
            ChoreCompletion(
                chore_id="c",
                child_id=vaiha.id,
                completed_at=now - dt.timedelta(days=days_ago),
                approved=True,
                points_awarded=pts,
            )
        )
    for reason, pts in (("Bonus: Tidy", 20), ("Pool refund: Lego", 500), ("Gift from Malia", 50), ("Fine", -40)):
        storage.add_points_transaction(PointsTransaction(child_id=vaiha.id, points=pts, reason=reason, created_at=now))
    with _at(now):
        rates = coord.earn_rates()
    assert rates == {vaiha.id: 21.4}  # (100 + 180 + 20) / 14
    assert malia.id not in rates


# ── 26: reward pictures ──────────────────────────────────────────────────

IMG = "/api/taskmate/image/" + "a" * 32 + ".jpg"
IMG2 = "/api/taskmate/image/" + "b" * 32 + ".jpg"


class TestPictures:
    def test_only_our_own_image_urls_are_kept(self):
        assert Reward.from_dict({"name": "x", "image_url": IMG + "?authSig=abc"}).image_url == IMG
        assert Reward.from_dict({"name": "x", "image_url": "https://evil.example/x.jpg"}).image_url == ""

    def test_replacing_or_purging_the_picture_removes_the_file(self):
        coord, storage, _mod, _vaiha, _malia = _system()
        reward = Reward(name="Cinema", cost=5, image_url=IMG)
        storage.add_reward(reward)
        with patch("custom_components.taskmate.images.async_delete_image", new=AsyncMock()) as delete:
            edited = storage.get_reward(reward.id)
            edited.image_url = IMG2
            with _at(_now()):
                run(coord.async_update_reward(edited))
            delete.assert_awaited_once_with(coord.hass, IMG)
            delete.reset_mock()
            with _at(_now()):
                run(coord.async_remove_reward(reward.id))
            # Kept while Recently deleted can still bring the reward back.
            delete.assert_not_awaited()
            later = dt_util.now() + dt.timedelta(days=8)
            with patch("custom_components.taskmate.coord_trash.dt_util.now", return_value=later):
                run(coord.async_purge_recently_deleted())
            delete.assert_awaited_once_with(coord.hass, IMG2)

    def test_a_picture_another_reward_shows_is_kept(self):
        coord, storage, _mod, _vaiha, _malia = _system()
        a = Reward(name="A", cost=5, image_url=IMG)
        b = Reward(name="B", cost=5, image_url=IMG)
        storage.add_reward(a)
        storage.add_reward(b)
        with patch("custom_components.taskmate.images.async_delete_image", new=AsyncMock()) as delete:
            with _at(_now()):
                run(coord.async_remove_reward(a.id))
            delete.assert_not_awaited()

    def test_the_sensor_signs_the_picture_only_when_set(self):
        coord, storage, _mod, _vaiha, _malia = _system()
        storage.add_reward(Reward(name="Cinema", cost=5, image_url=IMG))
        storage.add_reward(Reward(name="Sweets", cost=5))
        coord.data = coord._build_data_snapshot()
        with patch("custom_components.taskmate.images.sign_image_url", side_effect=lambda _h, u: u + "?authSig=x"):
            rows = {
                r["name"]: r for r in sensor_module._build_rewards_list(sensor_module._compute_common(coord), coord)
            }
        assert rows["Cinema"]["image_url"] == IMG + "?authSig=x"
        assert "image_url" not in rows["Sweets"]

    def test_websocket_strips_the_signature_and_refuses_foreign_urls(self):
        import voluptuous as vol

        from custom_components.taskmate.websocket import _reward_payload_schema

        schema = vol.Schema(_reward_payload_schema(require_name=False))
        assert schema({"image_url": IMG + "?authSig=x"})["image_url"] == IMG
        with pytest.raises(vol.Invalid):
            schema({"image_url": "javascript:alert(1)"})


# ── 18: printable vouchers ───────────────────────────────────────────────


class TestVoucher:
    def test_the_page_escapes_everything_it_shows(self):
        html = voucher.build_voucher(
            reward_name="<script>x</script>",
            child_name="Vaiha & co",
            cost=40,
            date_text="23 Oct 2026",
            buyer_name="<b>Malia</b>",
            labels={"for": "Für: {name}", "evil": "{name.__class__}"},
        )
        assert "<script>x" not in html and "&lt;script&gt;" in html
        assert "Für: Vaiha &amp; co" in html
        assert "&lt;b&gt;Malia" in html
        assert "Earned with 40 Stars · 23 Oct 2026" in html
        assert "Signed:" in html

    def test_no_gift_line_without_a_buyer(self):
        html = voucher.build_voucher(reward_name="Xbox", child_name="V", cost=1, date_text="d")
        assert "A present from" not in html


@pytest.fixture
async def ws_setup(hass):
    from custom_components.taskmate.const import DOMAIN
    from custom_components.taskmate.coordinator import TaskMateCoordinator
    from custom_components.taskmate.storage import TaskMateStorage

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.entry_id = "voucher_test"
    coord.storage = TaskMateStorage(hass, "voucher_test")
    await coord.storage.async_load()
    coord.async_record_audit = AsyncMock()
    hass.data = {DOMAIN: {"voucher_test": coord}}
    with patch.object(TaskMateCoordinator, "async_refresh", new=AsyncMock()):
        child = await coord.async_add_child("Vaiha")
        reward = Reward(name="30 min <Xbox>", cost=40)
        coord.storage.add_reward(reward)
        approved = RewardClaim(
            reward_id=reward.id, child_id=child.id, claimed_at=_now(), approved=True, approved_at=_now()
        )
        approved.approved_cost = 35
        pending = RewardClaim(reward_id=reward.id, child_id=child.id, claimed_at=_now())
        coord.storage.add_reward_claim(approved)
        coord.storage.add_reward_claim(pending)
    return coord, approved, pending


def _conn(admin):
    connection = MagicMock()
    connection.user.is_admin = admin
    return connection


@pytest.mark.asyncio
async def test_voucher_command_is_admin_only(ws_setup, hass):
    from custom_components.taskmate import websocket_rewards_extra as wsx

    _coord, approved, _pending = ws_setup
    connection = _conn(False)
    await wsx.ws_print_reward_voucher(
        hass, connection, {"id": 1, "type": wsx.WS_PRINT_VOUCHER, "claim_id": approved.id}
    )
    assert connection.send_error.call_args[0][1] == wsx.websocket_api.const.ERR_UNAUTHORIZED
    connection.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_voucher_command_prints_approved_claims_only(ws_setup, hass):
    from custom_components.taskmate import websocket_rewards_extra as wsx

    _coord, approved, pending = ws_setup
    connection = _conn(True)
    msg = {"id": 2, "type": wsx.WS_PRINT_VOUCHER, "claim_id": approved.id, "date_text": "23 Oct 2026"}
    await wsx.ws_print_reward_voucher(hass, connection, msg)
    html = connection.send_result.call_args[0][1]["html"]
    assert "30 min &lt;Xbox&gt;" in html and "For: Vaiha" in html and "Earned with 35" in html
    connection = _conn(True)
    await wsx.ws_print_reward_voucher(hass, connection, {**msg, "claim_id": pending.id})
    assert connection.send_error.call_args[0][1] == "not_found"
    connection.send_result.assert_not_called()
