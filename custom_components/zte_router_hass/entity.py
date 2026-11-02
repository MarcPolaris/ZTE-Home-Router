"""Shared helpers for ZTE Router entities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ZTEDataUpdateCoordinator


def uptime_to_datetime(seconds: float | int | None) -> datetime | None:
    """Convert an uptime in seconds to the boot time as a datetime."""
    if not seconds:
        return None
    try:
        boot = datetime.now(timezone.utc) - timedelta(seconds=float(seconds))
        return boot.replace(microsecond=0)
    except (TypeError, ValueError):
        return None


def build_device_info(coordinator: ZTEDataUpdateCoordinator) -> DeviceInfo:
    """Device registry entry shared by every entity of this router."""
    device = coordinator.data.get("device", {}) if coordinator.data else {}
    serial = device.get("serial_number") or coordinator.entry.data["host"]
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=coordinator.device_name,
        manufacturer=MANUFACTURER,
        model=device.get("model") or "ZTE Router",
        sw_version=device.get("software_version"),
        hw_version=device.get("hardware_version"),
        serial_number=serial,
    )


class ZTEEntity(CoordinatorEntity[ZTEDataUpdateCoordinator]):
    """Base entity bound to the ZTE router device."""

    _attr_should_poll = False
    # Entity names come from the translation keys of each description and are
    # prefixed with the device name by Home Assistant.
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZTEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.data.get("device", {}) if coordinator.data else {}
        serial = device.get("serial_number") or coordinator.entry.data["host"]
        self._attr_device_info = build_device_info(coordinator)
        self._attr_unique_id_base = serial

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


def dig(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    """Safely walk nested dicts."""
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
        if node is None:
            return default
    return node
