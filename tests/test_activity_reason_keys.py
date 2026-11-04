"""Transactions carry a translation key for their reason (#771).

The activity list showed the stored English reason ("Challenge reversed: E2E
Test Challenge") in every language. New rows also store ``reason_key`` and
``reason_params`` so the cards and the panel can render the reason in the
reader's language; ``reason`` keeps the English text for older readers.
"""

from __future__ import annotations

import json
import pathlib
import re
from unittest.mock import patch

from custom_components.taskmate.models import PointsTransaction

from .test_completion_eligibility import _make_system, _now, run

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"


def test_the_key_round_trips_and_old_rows_load_without_one():
    t = PointsTransaction(
        child_id="k", points=5, reason="Bonus: Tidy", reason_key="bonus", reason_params={"name": "Tidy"}
    )
    back = PointsTransaction.from_dict(t.to_dict())
    assert (back.reason, back.reason_key, back.reason_params) == ("Bonus: Tidy", "bonus", {"name": "Tidy"})
    old = PointsTransaction.from_dict({"child_id": "k", "points": 5, "reason": "Bonus: Tidy"})
    assert old.reason_key == "" and old.reason_params == {}
    assert "reason_key" not in PointsTransaction(child_id="k", points=1, reason="x").to_dict(), "only when set"


def test_add_and_remove_points_store_the_key():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        run(coord.async_add_points(kid.id, 5, reason="Surprise bonus 🎉", reason_key="surprise_bonus"))
        run(coord.async_remove_points(kid.id, 2, reason="Allowance payout", reason_key="allowance_payout"))
    rows = storage.get_points_transactions()
    assert [(t.reason_key, t.reason) for t in rows][-2:] == [
        ("surprise_bonus", "Surprise bonus 🎉"),
        ("allowance_payout", "Allowance payout"),
    ]


def test_the_activity_sensor_publishes_the_key():
    src = (ROOT / "sensor.py").read_text(encoding="utf-8")
    assert '"reason_key": t.reason_key' in src and '"reason_params": dict(t.reason_params)' in src


def test_every_stored_key_has_a_translation_in_every_locale():
    keys = set()
    for path in ROOT.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        keys |= set(re.findall(r'reason_key="([a-z_]+)"', src))
        keys |= set(re.findall(r'_log_streak_freeze\([^)]*?"(streak_freeze_[a-z]+)"', src, re.S))
        keys |= set(re.findall(r'key="(wish_[a-z_]+)"', src))
    keys |= {"wish_refund_declined", "wish_refund_removed"}
    keys |= {v for v in re.findall(r'"(pool_refund_[a-z_]+)"', (ROOT / "coord_rewards.py").read_text(encoding="utf-8"))}
    assert len(keys) >= 40, sorted(keys)
    for path in sorted((ROOT / "www" / "locales").glob("*.json")):
        loc = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(k for k in keys if f"activity.reason_{k}" not in loc)
        assert missing == [], f"{path.name} lacks {missing}"


def test_the_challenge_reversal_from_the_report_carries_its_key():
    src = (ROOT / "coord_challenges.py").read_text(encoding="utf-8")
    assert 'reason_key="challenge_reversed"' in src and 'reason_key="challenge_complete"' in src
