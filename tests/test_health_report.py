"""Health & diagnostics (#682).

Surfaces what is actually broken — orphaned references, config that can never
work, entities that no longer exist — with a severity, a plain sentence and
where to go and fix it.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate.models import Child, Chore, MandatoryMiss, Reward

from .test_coordinator_logic import _make_coord


def _coord(children=(), chores=(), rewards=(), completions=(), *,
           badges=(), scheduled=(), misses=(), allowlist=(), known_entities=()):
    settings = {"unlock_allowlist": list(allowlist), "active_unlocks": []}
    coord = _make_coord(settings=settings, children=list(children), completions=list(completions))
    coord.storage.get_chores = MagicMock(return_value=list(chores))
    coord.storage.get_rewards = MagicMock(return_value=list(rewards))
    coord.storage.get_completions = MagicMock(return_value=list(completions))
    coord.storage.get_badges = MagicMock(return_value=list(badges))
    coord.storage.get_scheduled_changes = MagicMock(return_value=list(scheduled))
    coord.storage.get_mandatory_misses = MagicMock(return_value=list(misses))
    coord.storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    coord.storage.data = {"children": [], "chores": []}
    coord.storage._data_version = 7
    known = set(known_entities)
    coord.hass.states.get = MagicMock(side_effect=lambda e: MagicMock() if e in known else None)
    return coord


def _codes(report):
    return {i["code"] for i in report["issues"]}


KID = Child(name="Ella", id="kid1")


class TestOrphans:
    def test_chore_assigned_to_a_deleted_child(self):
        chore = Chore(name="Ghost", id="c1", assigned_to=["gone"])
        assert "chore_orphan_assignee" in _codes(_coord([KID], [chore]).health_report())

    def test_reward_assigned_to_a_deleted_child(self):
        reward = Reward(name="Ghost", id="r1", assigned_to=["gone"])
        assert "reward_orphan_assignee" in _codes(_coord([KID], [], [reward]).health_report())

    def test_dependency_on_a_deleted_chore_is_an_error(self):
        """The chore can never unlock — that's broken, not untidy."""
        chore = Chore(name="Blocked", id="c1", depends_on=["gone"])
        report = _coord([KID], [chore]).health_report()
        assert "chore_orphan_dependency" in _codes(report)
        assert any(i["severity"] == "error" for i in report["issues"])

    def test_completion_for_a_deleted_chore(self):
        comp = MagicMock()
        comp.chore_id = "gone"
        comp.child_id = KID.id
        report = _coord([KID], [], [], [comp]).health_report()
        assert "completion_orphan" in _codes(report)

    def test_clean_setup_reports_nothing(self):
        chore = Chore(name="Fine", id="c1", assigned_to=[KID.id])
        report = _coord([KID], [chore]).health_report()
        assert report["issues"] == []
        assert report["healthy"] is True


class TestBrokenConfig:
    def test_missing_visibility_entity(self):
        chore = Chore(name="Gated", id="c1", assigned_to=[KID.id],
                      visibility_entity="binary_sensor.gone")
        assert "chore_missing_entity" in _codes(_coord([KID], [chore]).health_report())

    def test_missing_weather_entity(self):
        chore = Chore(name="Outdoor", id="c1", assigned_to=[KID.id],
                      weather_entity="weather.gone")
        assert "chore_missing_entity" in _codes(_coord([KID], [chore]).health_report())

    def test_present_entity_is_not_flagged(self):
        chore = Chore(name="Outdoor", id="c1", assigned_to=[KID.id],
                      weather_entity="weather.home")
        report = _coord([KID], [chore], known_entities={"weather.home"}).health_report()
        assert "chore_missing_entity" not in _codes(report)

    def test_reward_unlocking_a_revoked_entity(self):
        """It will silently do nothing on approval — worth saying so."""
        reward = Reward(name="TV", id="r1", unlock_entity="switch.tv")
        report = _coord([KID], [], [reward], allowlist=["switch.other"]).health_report()
        assert "reward_unlock_not_allowed" in _codes(report)

    def test_allowlisted_unlock_is_fine(self):
        reward = Reward(name="TV", id="r1", unlock_entity="switch.tv")
        report = _coord([KID], [], [reward], allowlist=["switch.tv"]).health_report()
        assert "reward_unlock_not_allowed" not in _codes(report)

    def test_child_with_no_chores(self):
        assert "child_without_chores" in _codes(_coord([KID], []).health_report())

    def test_everyone_chore_counts_for_every_child(self):
        """An empty assigned_to means everyone, so nobody is choreless."""
        chore = Chore(name="Open", id="c1", assigned_to=[])
        assert "child_without_chores" not in _codes(_coord([KID], [chore]).health_report())

    def test_disabled_chore_does_not_count_as_coverage(self):
        chore = Chore(name="Off", id="c1", assigned_to=[KID.id], enabled=False)
        assert "child_without_chores" in _codes(_coord([KID], [chore]).health_report())


class TestShape:
    def test_counts_are_reported(self):
        chore = Chore(name="Fine", id="c1", assigned_to=[KID.id])
        misses = [MandatoryMiss(chore_id="c1", child_id=KID.id,
                                due_date="2026-01-01", period_id="anytime")]
        report = _coord([KID], [chore], misses=misses).health_report()
        assert report["counts"]["children"] == 1
        assert report["counts"]["chores"] == 1
        assert report["counts"]["enabled_chores"] == 1
        assert report["counts"]["mandatory_misses"] == 1

    def test_storage_size_is_measured(self):
        assert _coord([KID], []).health_report()["storage_bytes"] > 0

    def test_errors_sort_above_warnings_and_notes(self):
        chore = Chore(name="Broken", id="c1", assigned_to=["gone"], depends_on=["gone"])
        severities = [i["severity"] for i in _coord([KID], [chore]).health_report()["issues"]]
        assert severities == sorted(severities, key=lambda s: {"error": 0, "warning": 1, "info": 2}[s])

    def test_notes_alone_still_count_as_healthy(self):
        """An informational note isn't something to worry about."""
        comp = MagicMock()
        comp.chore_id = "gone"
        comp.child_id = KID.id
        chore = Chore(name="Fine", id="c1", assigned_to=[KID.id])
        report = _coord([KID], [chore], [], [comp]).health_report()
        assert {i["severity"] for i in report["issues"]} == {"info"}
        assert report["healthy"] is True

    def test_every_issue_says_where_to_fix_it(self):
        chore = Chore(name="Broken", id="c1", assigned_to=["gone"], depends_on=["gone"])
        report = _coord([KID], [chore]).health_report()
        assert report["issues"]
        for issue in report["issues"]:
            assert issue["where"]
            assert issue["message"]
            assert issue["severity"] in ("error", "warning", "info")
