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
