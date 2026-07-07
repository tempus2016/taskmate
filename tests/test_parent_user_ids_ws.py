"""WS update_settings accepts and persists parent_user_ids (#661)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws


def _settings_schema():
    return (
        vol.Schema(ws._UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA),
        ws.WS_UPDATE_SETTINGS,
    )


def test_schema_accepts_parent_user_ids():
    schema, cmd = _settings_schema()
    schema({"type": cmd, "id": 1, "parent_user_ids": ["a", "b"]})  # must not raise


def test_schema_rejects_non_string_parent_user_ids():
    schema, cmd = _settings_schema()
    with pytest.raises(vol.Invalid):
        schema({"type": cmd, "id": 1, "parent_user_ids": [1, 2]})


@pytest.mark.asyncio
async def test_handler_persists_parent_user_ids(monkeypatch):
    coord = MagicMock()
    coord.storage.set_parent_user_ids = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    monkeypatch.setattr(ws, "_get_coordinator", lambda hass: coord)

    connection = MagicMock()
    connection.user.is_admin = True
    hass = MagicMock()
    msg = {"id": 1, "type": ws.WS_UPDATE_SETTINGS, "parent_user_ids": ["mum-uid", "mum-uid"]}

    await ws._ws_update_settings(hass, connection, msg)

    coord.storage.set_parent_user_ids.assert_called_once_with(["mum-uid", "mum-uid"])
    args, _ = connection.send_result.call_args
    assert "parent_user_ids" in args[1]["updated"]


@pytest.mark.asyncio
async def test_handler_rejects_non_admin(monkeypatch):
    coord = MagicMock()
    monkeypatch.setattr(ws, "_get_coordinator", lambda hass: coord)
    connection = MagicMock()
    connection.user.is_admin = False
    msg = {"id": 1, "type": ws.WS_UPDATE_SETTINGS, "parent_user_ids": ["x"]}

    await ws._ws_update_settings(MagicMock(), connection, msg)

    connection.send_error.assert_called_once()
    assert connection.send_error.call_args.args[1] == ws.websocket_api.const.ERR_UNAUTHORIZED
    connection.send_result.assert_not_called()
