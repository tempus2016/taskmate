"""Tests for TaskMate conversation intents (FEAT-12)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate import intents
from custom_components.taskmate.models import Child


def _coord(children, *, due=0, points_name="Stars"):
    c = MagicMock()
    c.storage.get_children = MagicMock(return_value=children)
    c.storage.get_points_name = MagicMock(return_value=points_name)
    c.get_due_chores_for_child = MagicMock(return_value=[object()] * due)
    return c


def test_find_child_case_insensitive():
    kids = [Child(name="Malia", id="k1"), Child(name="Alex", id="k2")]
    c = _coord(kids)
    assert intents._find_child(c, "malia").id == "k1"
    assert intents._find_child(c, "  ALEX ").id == "k2"
    assert intents._find_child(c, "nobody") is None


def test_chores_left_speech_variants():
    kids = [Child(name="Malia", id="k1")]
    assert "couldn't find" in intents.chores_left_speech(_coord(kids), "ghost")
    assert intents.chores_left_speech(_coord(kids, due=0), "Malia").startswith("Malia has finished")
    assert "1 chore left" in intents.chores_left_speech(_coord(kids, due=1), "Malia")
    assert "3 chores left" in intents.chores_left_speech(_coord(kids, due=3), "Malia")


def test_points_speech():
    kids = [Child(name="Alex", id="k2", points=42)]
    assert intents.points_speech(_coord(kids, points_name="Stars"), "Alex") == "Alex has 42 Stars."
    assert "couldn't find" in intents.points_speech(_coord(kids), "ghost")


def test_setup_registers_every_intent():
    hass = MagicMock()
    intents.intent.async_register.reset_mock()
    intents.async_setup_intents(hass)
    assert intents.intent.async_register.call_count == 5
    types = {type(call.args[1]).__name__ for call in intents.intent.async_register.call_args_list}
    assert types == {
        "ChoresLeftIntentHandler",
        "PointsIntentHandler",
        "CompleteChoreIntentHandler",
        "NextChoreIntentHandler",
        "RewardProgressIntentHandler",
    }


# ── Completing, next job and reward progress by voice ──────────────────────

from unittest.mock import AsyncMock  # noqa: E402

from custom_components.taskmate.models import Chore, Reward  # noqa: E402


def _voice_coord(*, due=(), chores=(), rewards=(), points=30, completion=None):
    kid = Child(name="Malia", id="k1", points=points)
    c = _coord([kid])
    c.get_due_chores_for_child = MagicMock(return_value=list(due))
    c.storage.get_chores = MagicMock(return_value=list(chores or due))
    c.storage.get_rewards = MagicMock(return_value=list(rewards))
    c.teamwork_size = MagicMock(return_value=0)
    c.async_complete_chore = AsyncMock(return_value=completion)
    return c


def _run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


def test_best_match_prefers_exact_then_contains_then_words():
    items = [Chore(name="Make bed", id="a"), Chore(name="Make breakfast", id="b"), Chore(name="Bins", id="c")]
    assert intents._best_match(items, "make bed").id == "a"
    assert intents._best_match(items, "the bins").id == "c"
    assert intents._best_match(items, "breakfast please").id == "b"
    assert intents._best_match(items, "hoover") is None


def test_complete_by_voice_ticks_the_matching_due_chore():
    bed = Chore(name="Make bed", id="bed", requires_approval=False)
    done = MagicMock(approved=True, points_awarded=5)
    c = _voice_coord(due=[bed], completion=done)
    speech = _run(intents.async_complete_by_voice(MagicMock(), c, "malia", "make bed"))
    c.async_complete_chore.assert_awaited_once_with("bed", "k1")
    assert "Make bed" in speech and "+5" in speech


def test_complete_by_voice_waiting_for_approval_says_so():
    bed = Chore(name="Make bed", id="bed")
    c = _voice_coord(due=[bed], completion=MagicMock(approved=False))
    assert "grown-up" in _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "bed"))


def test_complete_by_voice_refuses_what_a_voice_can_not_do():
    photo = Chore(name="Tidy room", id="t", require_photo=True)
    c = _voice_coord(due=[photo])
    assert "card" in _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "tidy room"))
    c.async_complete_chore.assert_not_awaited()


def test_complete_by_voice_already_done_and_unknown():
    bed = Chore(name="Make bed", id="bed")
    c = _voice_coord(due=[], chores=[bed])
    assert "already done" in _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "make bed"))
    assert "couldn't find a chore" in _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "walk the cat"))


def test_complete_by_voice_obeys_the_linked_child_rule(monkeypatch):
    from custom_components.taskmate import authz

    monkeypatch.setattr(authz, "async_context_allows_child", AsyncMock(return_value=False))
    c = _voice_coord(due=[Chore(name="Make bed", id="bed")])
    speech = _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "make bed", context=MagicMock()))
    assert "can't" in speech
    c.async_complete_chore.assert_not_awaited()


def test_next_chore_speech():
    c = _voice_coord(due=[Chore(name="Feed the cat", id="cat")])
    assert intents.next_chore_speech(c, "Malia") == "Malia's next job is Feed the cat."


def test_reward_progress_named_and_nearest():
    rewards = [Reward(name="Cinema trip", id="r1", cost=100), Reward(name="Sweets", id="r2", cost=20)]
    c = _voice_coord(rewards=rewards, points=30)
    assert intents.reward_progress_speech(c, "Malia", "the cinema trip") == "Malia needs 70 more Stars for Cinema trip."
    assert intents.reward_progress_speech(c, "Malia", "sweets") == "Malia has enough for Sweets!"
    assert intents.reward_progress_speech(c, "Malia") == "Malia needs 70 more Stars for Cinema trip."
    assert "couldn't find a reward" in intents.reward_progress_speech(c, "Malia", "pony")


def test_every_language_ships_sentences_for_every_intent():
    import pathlib

    import yaml

    root = pathlib.Path(__file__).resolve().parent.parent / "custom_sentences"
    langs = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert langs == ["da", "de", "en", "fr", "nb", "nn", "pl", "pt", "pt-BR"]
    wanted = {
        intents.INTENT_CHORES_LEFT,
        intents.INTENT_POINTS,
        intents.INTENT_COMPLETE_CHORE,
        intents.INTENT_NEXT_CHORE,
        intents.INTENT_REWARD_PROGRESS,
    }
    for lang in langs:
        data = yaml.safe_load((root / lang / "taskmate.yaml").read_text(encoding="utf-8"))
        assert data["language"] == lang
        assert set(data["intents"]) == wanted, lang


def test_saying_a_finished_chore_again_does_not_pick_a_similar_one():
    bed = Chore(name="Make bed", id="bed")
    ref = Chore(name="Make bed (reference)", id="ref")
    c = _voice_coord(due=[ref], chores=[bed, ref])
    assert "already done" in _run(intents.async_complete_by_voice(MagicMock(), c, "Malia", "make bed"))
    c.async_complete_chore.assert_not_awaited()


def test_reply_follows_the_language_of_the_question():
    import asyncio

    from custom_components.taskmate import notify_strings

    hass = MagicMock()
    hass.config.language = "en-GB"
    hass.async_add_executor_job = lambda fn, *a: asyncio.sleep(0, result=fn(*a))
    kid = Child(name="Malia", id="k1", points=7)
    c = _coord([kid])
    c.hass = hass
    obj = MagicMock(language="de", hass=hass)

    async def ask():
        await intents._prepare_reply(obj)
        return intents.points_speech(c, "Malia")

    assert _run(ask()) == "Malia hat 7 Stars."
    notify_strings._cache.pop("de", None)
