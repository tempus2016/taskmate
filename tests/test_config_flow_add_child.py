"""Regression tests for the add_child config-flow schema.

Issue #208: Submitting the Add New Child form without filling in the optional
availability_entity field raised "Entity is neither a valid entity ID nor a
valid UUID" because the schema used ``default=""`` on an EntitySelector field.
HA's EntitySelector validates the value (including the default) and rejects
empty strings.

Two levels of testing:

1. Pattern-level (TestAddChildSchemaBug / TestAddChildSchemaFixed) — pure
   voluptuous schemas that reproduce the exact failure mode using a validator
   that mimics HA's EntitySelector behaviour.  Proves the bug is real and that
   removing the empty default resolves it.

2. Source-level regression guard (TestConfigFlowSourceRegression) — reads
   config_flow.py and verifies the buggy pattern (``vol.Optional(entity_field,
   default="")``) is not present.  Will fail if the fix is reverted.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import voluptuous as vol


# ---------------------------------------------------------------------------
# Shared helper — mimics HA EntitySelector's validation behaviour
# ---------------------------------------------------------------------------

def _ha_entity_selector(v):
    """Stand-in for HA's EntitySelector.

    The real selector raises vol.Invalid for values that are neither a dotted
    entity-id (``domain.name``) nor a UUID.  Empty string fails both checks.
    """
    if not v or "." not in str(v):
        raise vol.Invalid("Entity is neither a valid entity ID nor a valid UUID")
    return v


# ---------------------------------------------------------------------------
# Pattern-level schema helpers
# ---------------------------------------------------------------------------

def _buggy_schema():
    """The original (broken) schema: empty-string defaults on entity fields."""
    return vol.Schema({
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=120)),
        vol.Optional("availability_entity", default=""): _ha_entity_selector,
        vol.Optional("availability_inverted", default=False): bool,
        vol.Optional("unavailability_entity", default=""): _ha_entity_selector,
    })


def _fixed_schema():
    """The corrected schema: no default on optional entity fields."""
    return vol.Schema({
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=120)),
        vol.Optional("availability_entity"): _ha_entity_selector,
        vol.Optional("availability_inverted", default=False): bool,
        vol.Optional("unavailability_entity"): _ha_entity_selector,
    })


# ---------------------------------------------------------------------------
# 1. Pattern-level tests — prove the bug is real and the fix works
# ---------------------------------------------------------------------------

class TestAddChildSchemaBug:
    def test_fails_when_availability_entity_omitted(self):
        """Reproduces #208: default='' causes EntitySelector to reject the empty value."""
        with pytest.raises(vol.Invalid, match="valid entity ID"):
            _buggy_schema()({"name": "Alice"})

    def test_fails_for_unavailability_entity_too(self):
        """unavailability_entity has the same default='' problem."""
        with pytest.raises(vol.Invalid, match="valid entity ID"):
            _buggy_schema()({"name": "Alice", "availability_entity": "binary_sensor.x"})

    def test_succeeds_when_both_entity_fields_provided(self):
        """Sanity-check: the buggy schema works fine when the user fills in entities."""
        result = _buggy_schema()({
            "name": "Alice",
            "availability_entity": "binary_sensor.alice_home",
            "unavailability_entity": "calendar.alice_busy",
        })
        assert result["availability_entity"] == "binary_sensor.alice_home"


class TestAddChildSchemaFixed:
    def test_accepts_name_only(self):
        """After the fix: submitting just a name succeeds — entities absent from result."""
        result = _fixed_schema()({"name": "Alice"})
        assert result["name"] == "Alice"
        assert "availability_entity" not in result
        assert "unavailability_entity" not in result

    def test_handler_fallback_yields_empty_string(self):
        """The handler uses .get('availability_entity', '') or '' — must yield ''."""
        result = _fixed_schema()({"name": "Alice"})
        entity = result.get("availability_entity", "") or ""
        assert entity == ""

    def test_accepts_valid_entity_when_provided(self):
        """Providing a real entity still works after the fix."""
        result = _fixed_schema()({
            "name": "Alice",
            "availability_entity": "binary_sensor.alice_home",
            "unavailability_entity": "calendar.alice_busy",
        })
        assert result["availability_entity"] == "binary_sensor.alice_home"
        assert result["unavailability_entity"] == "calendar.alice_busy"

    def test_accepts_availability_without_unavailability(self):
        """Either entity field can be omitted independently."""
        result = _fixed_schema()({
            "name": "Bob",
            "availability_entity": "binary_sensor.bob_home",
        })
        assert result["availability_entity"] == "binary_sensor.bob_home"
        assert "unavailability_entity" not in result


# ---------------------------------------------------------------------------
# 2. Source-level regression guard — fails if the fix is ever reverted
# ---------------------------------------------------------------------------

_BUGGY_ENTITY_DEFAULT = re.compile(
    r"vol\.Optional\(\s*['\"](?:availability|unavailability)_entity['\"],\s*default\s*=\s*['\"]['\"]"
)

_CONFIG_FLOW = pathlib.Path(__file__).parent.parent / "custom_components" / "taskmate" / "config_flow.py"


class TestConfigFlowSourceRegression:
    def test_no_empty_default_on_entity_fields(self):
        """config_flow.py must not use vol.Optional(entity_field, default='').

        HA's EntitySelector rejects empty strings, so any optional entity field
        must omit the default entirely (HA treats missing == no value selected).
        """
        source = _CONFIG_FLOW.read_text()
        matches = _BUGGY_ENTITY_DEFAULT.findall(source)
        assert not matches, (
            f"Found {len(matches)} instance(s) of vol.Optional with empty default "
            f"on an entity field — this causes #208:\n  " + "\n  ".join(matches)
        )
