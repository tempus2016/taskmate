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


class FakeCoordinatorEntity:
    """Minimal stand-in so sensor.py's TaskMateBaseSensor can inherit from it."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


_ha_coordinator = MagicMock()
_ha_coordinator.DataUpdateCoordinator = FakeDataUpdateCoordinator
_ha_coordinator.CoordinatorEntity = FakeCoordinatorEntity


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


# ── homeassistant.components.websocket_api ───────────────────────────────────
# Decorators must be pass-throughs so handler functions remain awaitable in tests.

def _ws_command_decorator(schema):
    """Return the handler unchanged — schema is ignored in tests."""
    return lambda f: f


def _ws_async_response(f):
    """Pass-through — no wrapping needed in tests."""
    return f


_ha_websocket_api = MagicMock()
_ha_websocket_api.websocket_command = _ws_command_decorator
_ha_websocket_api.async_response = _ws_async_response
_ha_websocket_api.async_register_command = MagicMock()

_ha_websocket_api_const = MagicMock()
_ha_websocket_api_const.ERR_UNAUTHORIZED = "unauthorized"
_ha_websocket_api.const = _ha_websocket_api_const


# ── homeassistant.exceptions ────────────────────────────────────────────────

class FakeUnauthorized(Exception):
    """Stand-in for homeassistant.exceptions.Unauthorized."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args)


class FakeServiceValidationError(Exception):
    """Stand-in for homeassistant.exceptions.ServiceValidationError."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args)


_ha_exceptions = MagicMock()
_ha_exceptions.Unauthorized = FakeUnauthorized
_ha_exceptions.ServiceValidationError = FakeServiceValidationError


# ── homeassistant.helpers.event ─────────────────────────────────────────────

_ha_event = MagicMock()
_ha_event.async_track_time_change = MagicMock(return_value=lambda: None)


# ── homeassistant.components.sensor / helpers.entity / entity_platform ─────
# sensor.py pulls SensorEntity + SensorStateClass + DeviceInfo. These are only
# ever touched for type hints and base-class inheritance; a MagicMock class
# suffices for unit tests.

class _FakeSensorEntity:
    pass


class _FakeSensorStateClass:
    TOTAL = "total"
    MEASUREMENT = "measurement"


_ha_components_sensor = MagicMock()
_ha_components_sensor.SensorEntity = _FakeSensorEntity
_ha_components_sensor.SensorStateClass = _FakeSensorStateClass


class _FakeBinarySensorEntity:
    pass


_ha_components_binary_sensor = MagicMock()
_ha_components_binary_sensor.BinarySensorEntity = _FakeBinarySensorEntity


class _FakeDeviceInfo(dict):
    """DeviceInfo behaves like a TypedDict; accept kwargs like the real one."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class _FakeCalendarEntity:
    pass


class _FakeCalendarEvent:
    """Minimal stand-in storing the fields calendar.py sets / tests read."""

    def __init__(self, start, end, summary, description=None, **kwargs):
        self.start = start
        self.end = end
        self.summary = summary
        self.description = description
        for k, v in kwargs.items():
            setattr(self, k, v)


_ha_components_calendar = MagicMock()
_ha_components_calendar.CalendarEntity = _FakeCalendarEntity
_ha_components_calendar.CalendarEvent = _FakeCalendarEvent


_ha_helpers_entity = MagicMock()
_ha_helpers_entity.DeviceInfo = _FakeDeviceInfo


_ha_helpers_entity_platform = MagicMock()


# ── homeassistant.util.dt ────────────────────────────────────────────────────
# coordinator.py imports this as:  from homeassistant.util import dt as dt_util

_DEFAULT_NOW = _dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=_UTC)  # Wednesday


class _DtUtilMock:
    """Controllable drop-in for homeassistant.util.dt."""

    _now: _dt.datetime = _DEFAULT_NOW
    DEFAULT_TIME_ZONE = _UTC

    def now(self) -> _dt.datetime:
        return self._now

    def start_of_local_day(self) -> _dt.datetime:
        return self._now.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def as_local(dt: _dt.datetime) -> _dt.datetime:
        return dt  # treat everything as UTC in tests


dt_util_mock = _DtUtilMock()

_ha_util = MagicMock()
_ha_util.dt = dt_util_mock  # `from homeassistant.util import dt` resolves here


# ── Register all stubs ───────────────────────────────────────────────────────

# Build an explicit components mock so we can pin .websocket_api on it.
# If homeassistant.components is a plain MagicMock(), attribute access
# auto-generates a new MagicMock instead of returning our stub.
_ha_components = MagicMock()
_ha_components.websocket_api = _ha_websocket_api
_ha_components.calendar = _ha_components_calendar

sys.modules.update(
    {
        "homeassistant": MagicMock(),
        "homeassistant.core": _ha_core,
        "homeassistant.config_entries": MagicMock(),
        "homeassistant.const": MagicMock(),
        "homeassistant.exceptions": _ha_exceptions,
        "homeassistant.helpers": MagicMock(),
        "homeassistant.helpers.service": MagicMock(),
        "homeassistant.helpers.storage": _ha_storage_mod,
        "homeassistant.helpers.event": _ha_event,
        "homeassistant.helpers.update_coordinator": _ha_coordinator,
        "homeassistant.helpers.config_validation": MagicMock(),
        "homeassistant.helpers.entity": _ha_helpers_entity,
        "homeassistant.helpers.entity_platform": _ha_helpers_entity_platform,
        "homeassistant.components": _ha_components,
        "homeassistant.components.sensor": _ha_components_sensor,
        "homeassistant.components.binary_sensor": _ha_components_binary_sensor,
        "homeassistant.components.calendar": _ha_components_calendar,
        "homeassistant.components.websocket_api": _ha_websocket_api,
        "homeassistant.util": _ha_util,
        "homeassistant.util.dt": dt_util_mock,
        # Stub the frontend sub-module so __init__.py's relative import succeeds
        # without executing frontend.py (which has its own heavy HA dependencies).
        "custom_components.taskmate.frontend": MagicMock(),
        # Note: voluptuous is NOT mocked — let real schema validation run in tests
    }
)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hass():
    """Return a fresh FakeHass instance."""
    return FakeHass()


def run_async(coro, loop=None):
    """Run a coroutine synchronously in tests."""
    if loop is None:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return loop.run_until_complete(coro)
