"""Shared test configuration and Home Assistant stubs for TaskMate tests.

All homeassistant stubs are installed into sys.modules here, at module-load
time, so that any subsequent `from custom_components.taskmate.xxx import …`
statements resolve without needing a real HA installation.
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock
import datetime as _dt

import pytest

# ---------------------------------------------------------------------------
# Home Assistant stubs
# These must be in place BEFORE any integration module is imported.
# ---------------------------------------------------------------------------

_UTC = _dt.timezone.utc


# ── homeassistant.core ──────────────────────────────────────────────────────

class FakeHass:
    """Minimal mock of HomeAssistant."""

    def __init__(self):
        self.services = MagicMock()
        self.services.async_call = AsyncMock()
        self.bus = MagicMock()

    def async_create_task(self, coro):
        # Don't schedule; just close to avoid 'coroutine never awaited' warnings
        if asyncio.iscoroutine(coro):
            coro.close()
        return None


_ha_core = MagicMock()
_ha_core.HomeAssistant = FakeHass
_ha_core.callback = lambda f: f      # pass-through decorator
_ha_core.ServiceCall = MagicMock


# ── homeassistant.helpers.update_coordinator ────────────────────────────────

class FakeDataUpdateCoordinator:
    """Minimal base class that TaskMateCoordinator inherits from."""

    def __init__(self, hass, logger, *, name, update_interval=None):
        self.hass = hass
        self.data: dict = {}

    async def async_refresh(self):
        """No-op in tests unless overridden."""


_ha_coordinator = MagicMock()
_ha_coordinator.DataUpdateCoordinator = FakeDataUpdateCoordinator


# ── homeassistant.helpers.storage ───────────────────────────────────────────

class FakeStore:
    """In-memory Store substitute that avoids the filesystem."""

    def __init__(self, hass, version, key):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


_ha_storage_mod = MagicMock()
_ha_storage_mod.Store = FakeStore


# ── homeassistant.helpers.event ─────────────────────────────────────────────

_ha_event = MagicMock()
_ha_event.async_track_time_change = MagicMock(return_value=lambda: None)


# ── homeassistant.util.dt ────────────────────────────────────────────────────
# coordinator.py imports this as:  from homeassistant.util import dt as dt_util

_DEFAULT_NOW = _dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=_UTC)  # Wednesday


class _DtUtilMock:
    """Controllable drop-in for homeassistant.util.dt."""

    _now: _dt.datetime = _DEFAULT_NOW

    def now(self) -> _dt.datetime:
        return self._now

    @staticmethod
    def as_local(dt: _dt.datetime) -> _dt.datetime:
        return dt  # treat everything as UTC in tests


dt_util_mock = _DtUtilMock()

_ha_util = MagicMock()
_ha_util.dt = dt_util_mock  # `from homeassistant.util import dt` resolves here


# ── Register all stubs ───────────────────────────────────────────────────────

sys.modules.update(
    {
        "homeassistant": MagicMock(),
        "homeassistant.core": _ha_core,
        "homeassistant.config_entries": MagicMock(),
        "homeassistant.const": MagicMock(),
        "homeassistant.helpers": MagicMock(),
        "homeassistant.helpers.storage": _ha_storage_mod,
        "homeassistant.helpers.event": _ha_event,
        "homeassistant.helpers.update_coordinator": _ha_coordinator,
        "homeassistant.helpers.config_validation": MagicMock(),
        "homeassistant.util": _ha_util,
        "homeassistant.util.dt": dt_util_mock,
        # Stub the frontend sub-module so __init__.py's relative import succeeds
        # without executing frontend.py (which has its own heavy HA dependencies).
        "custom_components.taskmate.frontend": MagicMock(),
        # voluptuous is used by __init__.py for service schemas
        "voluptuous": MagicMock(),
    }
)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hass():
    """Return a fresh FakeHass instance."""
    return FakeHass()


@pytest.fixture
def event_loop():
    """Provide a fresh asyncio event loop per test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def run_async(coro, loop=None):
    """Run a coroutine synchronously in tests."""
    if loop is None:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return loop.run_until_complete(coro)
