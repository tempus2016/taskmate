"""WebSocket commands for the pet shop.

The catalogue editor and the purchase approvals are the admin panel's, so
admin-only like every panel command (and recorded in the audit log by
``_admin_only``). The pet card reads the shop for one child through
``taskmate/pet_shop/catalogue``, gated on the same linked-child rule as the
services, so the catalogue never has to ride on a sensor attribute. Children
buy and dress their pet through the ``buy_pet_item`` / ``equip_pet_item``
services.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_pet_shop import (
    PET_SHOP_COST_MAX,
    PET_SHOP_EMOJI_MAX,
    PET_SHOP_LEVEL_MAX,
    PET_SHOP_NAME_MAX,
    PET_SHOP_SLOTS,
)
from .websocket import _admin_only
from .websocket_recaps import _reader

WS_PET_SHOP_CATALOGUE = "taskmate/pet_shop/catalogue"
WS_PET_SHOP_SAVE_ITEM = "taskmate/pet_shop/save_item"
WS_PET_SHOP_SET_SHOWN = "taskmate/pet_shop/set_shown"
WS_PET_SHOP_REMOVE_ITEM = "taskmate/pet_shop/remove_item"
WS_PET_SHOP_RESET = "taskmate/pet_shop/reset"
WS_PET_SHOP_DECIDE = "taskmate/pet_shop/decide"


@websocket_api.websocket_command({vol.Required("type"): WS_PET_SHOP_CATALOGUE, vol.Required("child_id"): str})
@websocket_api.async_response
@_reader(check_child=True)
async def ws_pet_shop_catalogue(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], coordinator.pet_shop_for_child(msg["child_id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PET_SHOP_SAVE_ITEM,
        vol.Optional("item_id"): str,
        vol.Optional("name", default=""): vol.All(str, vol.Length(max=PET_SHOP_NAME_MAX)),
        vol.Required("emoji"): vol.All(str, vol.Length(min=1, max=PET_SHOP_EMOJI_MAX)),
        vol.Required("slot"): vol.In(PET_SHOP_SLOTS),
        vol.Required("cost"): vol.All(vol.Coerce(int), vol.Range(min=1, max=PET_SHOP_COST_MAX)),
        vol.Optional("level", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=PET_SHOP_LEVEL_MAX)),
        vol.Optional("shown", default=True): bool,
        vol.Optional("tint", default=""): vol.All(str, vol.Length(max=10)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_pet_shop_save_item(hass, connection, msg, coordinator):
    item = await coordinator.async_save_pet_shop_item(
        msg.get("item_id"),
        name=msg["name"],
        emoji=msg["emoji"],
        slot=msg["slot"],
        cost=msg["cost"],
        level=msg["level"],
        shown=msg["shown"],
        tint=msg["tint"],
    )
    connection.send_result(msg["id"], {"item": item})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_PET_SHOP_SET_SHOWN, vol.Required("item_id"): str, vol.Required("shown"): bool}
)
@websocket_api.async_response
@_admin_only
async def ws_pet_shop_set_shown(hass, connection, msg, coordinator):
    await coordinator.async_set_pet_shop_item_shown(msg["item_id"], msg["shown"])
    connection.send_result(msg["id"], {"item_id": msg["item_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_PET_SHOP_REMOVE_ITEM, vol.Required("item_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_pet_shop_remove_item(hass, connection, msg, coordinator):
    await coordinator.async_remove_pet_shop_item(msg["item_id"])
    connection.send_result(msg["id"], {"item_id": msg["item_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_PET_SHOP_RESET})
@websocket_api.async_response
@_admin_only
async def ws_pet_shop_reset(hass, connection, msg, coordinator):
    await coordinator.async_reset_pet_shop_items()
    connection.send_result(msg["id"], {"items": coordinator.pet_shop_items()})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_PET_SHOP_DECIDE, vol.Required("purchase_id"): str, vol.Required("approve"): bool}
)
@websocket_api.async_response
@_admin_only
async def ws_pet_shop_decide(hass, connection, msg, coordinator):
    await coordinator.async_decide_pet_purchase(msg["purchase_id"], msg["approve"])
    connection.send_result(msg["id"], {"purchase_id": msg["purchase_id"]})


PET_SHOP_COMMANDS = (
    ws_pet_shop_catalogue,
    ws_pet_shop_save_item,
    ws_pet_shop_set_shown,
    ws_pet_shop_remove_item,
    ws_pet_shop_reset,
    ws_pet_shop_decide,
)
