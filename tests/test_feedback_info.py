"""Help & feedback page: the environment summary it fills into a GitHub issue.

Counts and codes only — never who the family are — and every probe of HA or
HACS internals degrades to "unknown" instead of failing the page.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.models import Child, Chore, Reward

from .conftest import run_async

sys.modules.setdefault("homeassistant.loader", MagicMock())

from custom_components.taskmate import feedback  # noqa: E402


@pytest.fixture(autouse=True)
def _integration(monkeypatch):
    monkeypatch.setattr(feedback, "async_get_integration", AsyncMock(return_value=MagicMock(version="7.1.0")))
    monkeypatch.setattr(feedback.ha_const, "__version__", "2026.10.2", raising=False)


def _system_info(monkeypatch, value):
    mod = MagicMock()
    if isinstance(value, Exception):
        mod.async_get_system_info = AsyncMock(side_effect=value)
    else:
        mod.async_get_system_info = AsyncMock(return_value=value)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.system_info", mod)


def _hass(components=(), data=None):
    hass = MagicMock()
    hass.config.components = set(components)
    hass.config.language = "en-GB"
    hass.data = data or {}
    return hass


def _coord(health=None):
    coord = MagicMock()
    coord.config_entry = SimpleNamespace(entry_id="entry-1")
    storage = coord.storage
    storage.get_children.return_value = [
        Child(name="Malia", id="k1"),
        Child(name="Vaiha", id="k2"),
        Child(name="Sam", id="a1", is_adult=True),
    ]
    storage.get_chores.return_value = [Chore(name="Bins", id="c1"), Chore(name="Dishes", id="c2")]
    storage.get_rewards.return_value = [Reward(name="Film night", id="r1")]
    storage.get_settings.return_value = {"card_design": "graphite"}
    coord.health_report.return_value = health or {
        "healthy": False,
        "issues": [
            {"code": "chore_orphan_assignee", "message": "Bins is assigned to nobody", "severity": "warning"},
            {"code": "storage_large", "message": "x", "severity": "info"},
            {"code": "chore_orphan_assignee", "message": "dup", "severity": "warning"},
        ],
    }
    return coord


def _hacs(*, found=True, default=True, installed=True):
    repo = SimpleNamespace(data=SimpleNamespace(id=123456, installed=installed)) if found else None
    repos = MagicMock()
    repos.get_by_full_name.return_value = repo
    repos.is_default.return_value = default
    return SimpleNamespace(repositories=repos)


def test_summary_carries_versions_counts_and_codes(monkeypatch):
    _system_info(monkeypatch, {"installation_type": "Home Assistant Container"})
    out = run_async(feedback.async_feedback_info(_hass(), _coord()))
    assert out["integration_version"] == "7.1.0"
    assert out["ha_version"] == "2026.10.2"
    assert out["installation_type"] == "container"
    assert out["installation_type_raw"] == "Home Assistant Container"
    assert out["counts"] == {"children": 2, "adults": 1, "chores": 2, "rewards": 1}
    assert out["card_design"] == "graphite"
    assert out["health_codes"] == ["chore_orphan_assignee", "storage_large"]
    assert out["entry_id"] == "entry-1"
    assert out["language"] == "en-GB"


def test_summary_never_names_anyone(monkeypatch):
    _system_info(monkeypatch, {"installation_type": "Home Assistant OS"})
    text = repr(run_async(feedback.async_feedback_info(_hass(), _coord())))
    for name in ("Malia", "Vaiha", "Sam", "Bins", "Dishes", "Film night", "assigned to nobody"):
        assert name not in text


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Home Assistant OS", "haos"),
        ("Home Assistant Supervised", "supervised"),
        ("Home Assistant Container", "container"),
        ("Unsupported Third Party Container", "container"),
        ("Home Assistant Core", "core"),
        ("Something new", "unknown"),
    ],
)
def test_installation_types_map_to_the_template(monkeypatch, raw, key):
    _system_info(monkeypatch, {"installation_type": raw})
    assert run_async(feedback.async_feedback_info(_hass(), _coord()))["installation_type"] == key


def test_system_info_failure_is_unknown_not_an_error(monkeypatch):
    _system_info(monkeypatch, RuntimeError("boom"))
    out = run_async(feedback.async_feedback_info(_hass(), _coord()))
    assert out["installation_type"] == "unknown"
    assert out["installation_type_raw"] == ""


def test_install_method_without_hacs_is_manual():
    assert feedback._install_method(_hass()) == "manual"


def test_install_method_reads_hacs_default_and_custom():
    assert feedback._install_method(_hass(["hacs"], {"hacs": _hacs(default=True)})) == "hacs_default"
    assert feedback._install_method(_hass(["hacs"], {"hacs": _hacs(default=False)})) == "hacs_custom"


def test_hacs_without_taskmate_is_manual():
    assert feedback._install_method(_hass(["hacs"], {"hacs": _hacs(found=False)})) == "manual"
    assert feedback._install_method(_hass(["hacs"], {"hacs": _hacs(installed=False)})) == "manual"


def test_hacs_internals_changing_shape_is_unknown():
    assert feedback._install_method(_hass(["hacs"], {"hacs": object()})) == "unknown"
    assert feedback._install_method(_hass(["hacs"], {})) == "unknown"


def test_lovelace_mode_dataclass_and_legacy_dict():
    assert feedback._lovelace_mode(_hass(data={"lovelace": SimpleNamespace(resource_mode="storage")})) == "storage"
    # Before the rename the dataclass called it `mode`.
    assert feedback._lovelace_mode(_hass(data={"lovelace": SimpleNamespace(mode="yaml")})) == "yaml"
    assert feedback._lovelace_mode(_hass(data={"lovelace": {"mode": "yaml"}})) == "yaml"
    assert feedback._lovelace_mode(_hass(data={"lovelace": {"resource_mode": "YAML"}})) == "yaml"
    assert feedback._lovelace_mode(_hass(data={"lovelace": {"mode": "auto-gen"}})) == "unknown"
    assert feedback._lovelace_mode(_hass()) == "unknown"


def test_health_failure_leaves_codes_empty(monkeypatch):
    _system_info(monkeypatch, {"installation_type": "Home Assistant OS"})
    coord = _coord()
    coord.health_report.side_effect = RuntimeError("boom")
    assert run_async(feedback.async_feedback_info(_hass(), coord))["health_codes"] == []


def test_entry_id_falls_back_to_the_hass_data_key(monkeypatch):
    _system_info(monkeypatch, {"installation_type": "Home Assistant OS"})
    coord = _coord()
    coord.config_entry = None
    hass = _hass(data={"taskmate": {"entry-9": coord}})
    assert run_async(feedback.async_feedback_info(hass, coord))["entry_id"] == "entry-9"


def _connection(admin):
    conn = MagicMock()
    conn.user = SimpleNamespace(id="u1", name="Sam", is_admin=admin)
    return conn


def test_ws_command_is_admin_only(monkeypatch):
    monkeypatch.setattr(ws, "_get_coordinator", lambda hass: _coord())
    conn = _connection(admin=False)
    run_async(ws._ws_feedback_info(_hass(), conn, {"id": 1, "type": ws.WS_FEEDBACK_INFO}))
    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "unauthorized"
    conn.send_result.assert_not_called()


def test_ws_command_returns_the_summary_and_is_not_audited(monkeypatch):
    _system_info(monkeypatch, {"installation_type": "Home Assistant OS"})
    coord = _coord()
    coord.async_record_audit = AsyncMock()
    monkeypatch.setattr(ws, "_get_coordinator", lambda hass: coord)
    conn = _connection(admin=True)
    run_async(ws._ws_feedback_info(_hass(), conn, {"id": 1, "type": ws.WS_FEEDBACK_INFO}))
    result = conn.send_result.call_args[0][1]
    assert result["installation_type"] == "haos"
    coord.async_record_audit.assert_not_called()
    assert ws.WS_FEEDBACK_INFO in ws._AUDIT_EXCLUDE


def test_ws_command_is_registered():
    assert ws._ws_feedback_info in ws._COMMANDS
