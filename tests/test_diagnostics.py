"""Diagnostics download: useful for a bug report, but never says who the family are."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.models import Child, Chore, Reward

from .conftest import run_async


def _redact(data, keys):
    """The behaviour of HA's async_redact_data, for the stub."""
    if isinstance(data, list):
        return [_redact(v, keys) for v in data]
    if not isinstance(data, dict):
        return data
    return {
        k: ("**REDACTED**" if k in keys and v not in (None, "", [], {}) else _redact(v, keys)) for k, v in data.items()
    }


_diag_mod = MagicMock()
_diag_mod.async_redact_data = _redact
sys.modules["homeassistant.components.diagnostics"] = _diag_mod
_loader = MagicMock()
_loader.async_get_integration = AsyncMock(return_value=MagicMock(version="6.4.0"))
sys.modules["homeassistant.loader"] = _loader

from custom_components.taskmate import diagnostics  # noqa: E402


def _setup():
    coord = MagicMock()
    storage = coord.storage
    storage.data = {"completions": [1, 2, 3], "points_transactions": [], "notification_config": {}}
    storage.get_settings.return_value = {"ics_token": "secret", "card_design": "classic"}
    storage.get_points_name.return_value = "Stars"
    storage.get_children.return_value = [
        Child(name="Malia", id="k1", linked_user_id="u1", birthday="2018-05-01", notify_service="notify.mobile")
    ]
    storage.get_chores.return_value = [Chore(name="Bins", id="c1", description="Wheel them out", assigned_to=["k1"])]
    storage.get_rewards.return_value = [Reward(name="Film night", id="r1")]
    coord.health_report.return_value = {"healthy": True, "issues": []}
    coord.last_update_success = True
    hass = MagicMock()
    hass.data = {"taskmate": {"e1": coord}}
    entry = MagicMock(entry_id="e1", version=1, options={})
    diagnostics.er.async_entries_for_config_entry = MagicMock(
        return_value=[MagicMock(domain="sensor"), MagicMock(domain="sensor"), MagicMock(domain="button")]
    )
    return hass, entry


def test_diagnostics_redacts_people_and_secrets():
    hass, entry = _setup()
    out = run_async(diagnostics.async_get_config_entry_diagnostics(hass, entry))
    child = out["children"][0]
    assert child["name"] == "**REDACTED**"
    assert child["linked_user_id"] == "**REDACTED**"
    assert child["birthday"] == "**REDACTED**"
    assert child["notify_service"] == "**REDACTED**"
    assert child["id"] == "k1"
    assert out["settings"]["ics_token"] == "**REDACTED**"
    assert out["settings"]["card_design"] == "classic"
    assert "Malia" not in repr(out)
    assert "secret" not in repr(out)


def test_diagnostics_keeps_what_a_bug_report_needs():
    hass, entry = _setup()
    out = run_async(diagnostics.async_get_config_entry_diagnostics(hass, entry))
    assert out["loaded"] is True
    assert out["chores"][0]["name"] == "Bins"
    assert out["chores"][0]["assigned_to"] == ["k1"]
    assert out["chores"][0]["description"] == "**REDACTED**"
    assert out["rewards"][0]["name"] == "Film night"
    assert out["history_sizes"]["completions"] == 3
    assert out["entities"] == {"total": 3, "by_platform": {"button": 1, "sensor": 2}}
    assert out["health"] == {"healthy": True, "issues": []}


def test_diagnostics_when_not_loaded():
    hass, entry = _setup()
    hass.data = {"taskmate": {}}
    out = run_async(diagnostics.async_get_config_entry_diagnostics(hass, entry))
    assert out["loaded"] is False
    assert "children" not in out
