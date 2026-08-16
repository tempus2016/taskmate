"""Shared helpers for TaskMate entities."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def taskmate_device_info(entry_id: str) -> DeviceInfo:
    """Device info shared by every TaskMate entity."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="TaskMate",
        manufacturer="TaskMate",
        model="Family Chore Manager",
    )
