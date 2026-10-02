"""The resolver's companion sensor ids must match the entities that exist (#798).

`taskmate-attr-resolver.js` hardcodes the companion sensor ids it merges. A
typo there fails silently: the sensor is simply never found, the attributes it
owns go missing, and every card falls back to whatever partial data the overview
sensor happens to carry. `sensor.pending_approvals` sat wrong for exactly that
reason — the real entity is `sensor.taskmate_pending_approvals`, so approvals
left pending from a previous day, and missed mandatory chores, were invisible on
the approvals card.

These tests derive the expected ids from the sensor platform itself so the next
typo fails here rather than in someone's dashboard.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
RESOLVER = (ROOT / "www" / "taskmate-attr-resolver.js").read_text(encoding="utf-8")
SENSOR_SRC = (ROOT / "sensor.py").read_text(encoding="utf-8")

# The card layer treats this one as the primary entity, not a companion.
PRIMARY = "sensor.taskmate_overview"


def _companions() -> list[str]:
    """The COMPANIONS array as the browser sees it.

    Line comments are stripped first: the block is commented, and prose naming
    an entity id would otherwise be read as if it were an array entry.
    """
    block = re.search(r"const COMPANIONS = \[(.*?)\];", RESOLVER, re.S)
    assert block, "COMPANIONS array not found in the resolver"
    code = re.sub(r"//[^\n]*", "", block.group(1))
    return re.findall(r'"([^"]+)"', code)


def _entity_id(name: str) -> str:
    """Entity id Home Assistant generates for a TaskMate sensor.

    The sensors carry no `_attr_has_entity_name`, so the "TaskMate" device name
    prefixes the slug — and is not repeated when the entity name already starts
    with it. Verified against the running dev instance: this reproduces all
    seven real ids exactly.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"sensor.{slug}" if slug.startswith("taskmate_") else f"sensor.taskmate_{slug}"


def _static_sensor_entity_ids() -> set[str]:
    """Every non-per-child sensor. Per-child names are f-strings, so the plain
    string literals are exactly the singleton sensors."""
    return {_entity_id(n) for n in re.findall(r'self\._attr_name = "([^"]+)"', SENSOR_SRC)}


class TestCompanionIdsAreReal:
    def test_every_companion_is_an_entity_the_integration_creates(self):
        real = _static_sensor_entity_ids()
        bogus = [c for c in _companions() if c not in real]
        assert bogus == [], (
            f"resolver references sensors that do not exist: {bogus}. Real singleton sensors: {sorted(real)}"
        )

    def test_pending_approvals_is_the_taskmate_prefixed_id(self):
        """The regression itself: the sensor is named "Pending Approvals" but
        the device name still prefixes its entity id."""
        companions = _companions()
        assert "sensor.taskmate_pending_approvals" in companions
        assert "sensor.pending_approvals" not in companions

    def test_companions_cover_every_singleton_sensor_except_the_primary(self):
        """A sensor the resolver forgets is one whose attributes silently never
        reach a card pointed at the overview entity."""
        expected = _static_sensor_entity_ids() - {PRIMARY}
        assert set(_companions()) == expected

    def test_all_companions_carry_the_domain_prefix(self):
        """Cheap structural guard — every TaskMate entity id starts this way."""
        bad = [c for c in _companions() if not c.startswith("sensor.taskmate_")]
        assert bad == [], f"companion ids missing the taskmate_ prefix: {bad}"


def _skip_keys() -> dict[str, list[str]]:
    """COMPANION_SKIP_KEYS as the browser sees it (#834)."""
    block = re.search(r"const COMPANION_SKIP_KEYS = \{(.*?)\};", RESOLVER, re.S)
    assert block, "COMPANION_SKIP_KEYS object not found in the resolver"
    code = re.sub(r"//[^\n]*", "", block.group(1))
    out: dict[str, list[str]] = {}
    for entity, body in re.findall(r'"(sensor\.[a-z_]+)"\s*:\s*\[(.*?)\]', code, re.S):
        out[entity] = re.findall(r'"([^"]+)"', body)
    return out


def _pending_approvals_count_keys() -> list[str]:
    """Keys PendingApprovalsSensor publishes as a scalar count, not a list.

    Derived from sensor.py so adding a fourth count is caught here rather than
    by a user whose card goes blank.
    """
    block = re.search(r"class PendingApprovalsSensor.*?(?=\nclass |\Z)", SENSOR_SRC, re.S)
    assert block, "PendingApprovalsSensor not found in sensor.py"
    return re.findall(r'"([a-z_]+)":\s*len\(', block.group(0))


class TestCollidingAttributesAreNotMerged:
    """#834: two sensors used one name for two different shapes.

    sensor.taskmate_rewards owns `pending_reward_claims` as the LIST of claims;
    sensor.taskmate_pending_approvals published the same name as an integer
    count. The approvals sensor merges last, so the number won, and every card
    calling .filter()/.some() on it threw — the rewards card and the
    child-filtered approvals card both rendered as an empty box the moment a
    child claimed a reward.
    """

    def test_pending_approvals_counts_are_skipped_in_the_merge(self):
        counts = _pending_approvals_count_keys()
        assert counts, "expected PendingApprovalsSensor to publish count attributes"
        skipped = _skip_keys().get("sensor.taskmate_pending_approvals", [])
        missing = [k for k in counts if k not in skipped]
        assert missing == [], (
            f"PendingApprovalsSensor publishes {missing} as a scalar count, but the "
            "resolver still merges them. Any card reading one of these names as a "
            "list will throw and render blank."
        )

    def test_the_colliding_key_is_covered(self):
        """Pin the exact key from the bug report so this can't silently narrow."""
        skipped = _skip_keys().get("sensor.taskmate_pending_approvals", [])
        assert "pending_reward_claims" in skipped

    def test_skip_lists_only_name_real_companions(self):
        unknown = [e for e in _skip_keys() if e not in _companions()]
        assert unknown == [], f"skip list names non-companion sensors: {unknown}"


class TestOverviewPublishesRealEntityIds:
    """#1018: Home Assistant 2026.6+ prefixes a new entity's id with its
    device's area, so the bounties sensor came up as
    sensor.familie_taskmate_bounties and the bounty card found nothing. The
    overview publishes the ids the registry really holds."""

    def test_suffixes_match_the_resolver_defaults(self):
        from custom_components.taskmate.sensor import COMPANION_SUFFIXES

        assert [f"sensor.taskmate_{s}" for s in COMPANION_SUFFIXES] == _companions()

    def test_suffixes_are_the_companion_unique_ids(self):
        from custom_components.taskmate.sensor import COMPANION_SUFFIXES

        unique = set(re.findall(r'_attr_unique_id = f"\{entry\.entry_id\}_([a-z_]+)"', SENSOR_SRC))
        assert set(COMPANION_SUFFIXES) <= unique

    def _sensor(self, registry_ids: dict[str, str]):
        from unittest.mock import MagicMock, patch

        from custom_components.taskmate import sensor as sensor_mod
        from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

        from .test_sensor_attributes import _stress_coordinator

        coord = _stress_coordinator()
        coord.storage.get_children = MagicMock(return_value=[MagicMock(id="k1"), MagicMock(id="k2")])
        entry = MagicMock(entry_id="E")
        ent = TaskMateOverallStatsSensor(coord, entry)
        ent.hass = MagicMock()
        registry = MagicMock()
        registry.async_get_entity_id = lambda domain, platform, uid: registry_ids.get(uid)
        return ent, patch.object(sensor_mod.er, "async_get", return_value=registry)

    def test_map_carries_area_prefixed_ids(self):
        ent, patched = self._sensor(
            {
                "E_bounties": "sensor.familie_taskmate_bounties",
                "E_chores": "sensor.taskmate_chores",
                "E_k1_badges": "sensor.familie_taskmate_nils_badges",
            }
        )
        with patched:
            m = ent._entity_map()
        assert m["companion_entities"] == {
            "bounties": "sensor.familie_taskmate_bounties",
            "chores": "sensor.taskmate_chores",
        }
        assert m["badge_entities"] == {"k1": "sensor.familie_taskmate_nils_badges"}

    def test_no_hass_publishes_empty_maps(self):
        ent, patched = self._sensor({})
        ent.hass = None
        with patched:
            assert ent._entity_map() == {"companion_entities": {}, "badge_entities": {}}

    def test_map_is_unrecorded(self):
        from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

        assert {"companion_entities", "badge_entities"} <= TaskMateOverallStatsSensor._unrecorded_attributes
