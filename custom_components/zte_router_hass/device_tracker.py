"""Device tracker platform for ZTE Router (LAN devices)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTEDataUpdateCoordinator
from .entity import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device trackers for all known LAN devices."""
    coordinator: ZTEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_macs: set[str] = set()

    @callback
    def async_update_trackers() -> None:
        """Add trackers for newly seen devices."""
        new_entities = []
        for device in coordinator.lan_devices:
            mac = device.get("mac")
            if not mac or mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.append(ZTEDeviceTracker(coordinator, device))
        if new_entities:
            async_add_entities(new_entities)

    # add entities for whatever the first refresh already saw,
    # and keep listening for newly connected devices
    async_update_trackers()
    entry.async_on_unload(coordinator.async_add_listener(async_update_trackers))


class ZTEDeviceTracker(CoordinatorEntity[ZTEDataUpdateCoordinator], ScannerEntity):
    """Representation of a LAN/WiFi device tracked by the ZTE router."""

    _attr_should_poll = False
    # keep all LAN devices grouped in the router's diagnostic section
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ZTEDataUpdateCoordinator, device: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._attr_device_info = build_device_info(coordinator)
        self._mac = device["mac"]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_tracker_{self._mac}"
        self._update_from_device(device)

    def _current_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.lan_devices:
            if device.get("mac") == self._mac:
                return device
        return None

    def _update_from_device(self, device: dict[str, Any]) -> None:
        hostname = device.get("hostname") or self._mac
        self._attr_name = hostname
        # enrich with the per-client detail the app page exposes
        # (vue_client_data): alias, IPv6 addresses, live rates, last seen
        detail = (self.coordinator.data or {}).get("clients", {}).get(self._mac, {})
        self._attr_extra_state_attributes = {
            "mac": self._mac,
            "ip": device.get("ip"),
            "connection_type": device.get("connection_type"),
            "interface": device.get("interface"),
            "band": device.get("band") or None,
            "rssi": device.get("rssi") or None,
            "is_guest": device.get("is_guest"),
            "parent_device": device.get("parent_device") or None,
            "device_type": device.get("device_type") or None,
            "rx_bytes": device.get("rx_bytes"),
            "tx_bytes": device.get("tx_bytes"),
            "ipv6": detail.get("ipv6") or None,
            "ipv6_gua": detail.get("ipv6_gua") or None,
            "alias": detail.get("alias") or None,
            "iface_type": detail.get("iface_type") or None,
            "last_connection": detail.get("last_connection") or None,
            "up_rate": detail.get("up_rate") or None,
            "down_rate": detail.get("down_rate") or None,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self._current_device()
        if device:
            self._update_from_device(device)
        self.async_write_ha_state()

    @property
    def ip_address(self) -> str | None:
        device = self._current_device()
        return device.get("ip") if device else None

    @property
    def mac_address(self) -> str | None:
        return self._mac

    @property
    def hostname(self) -> str | None:
        device = self._current_device()
        return device.get("hostname") if device else None

    @property
    def is_connected(self) -> bool:
        device = self._current_device()
        return bool(device and device.get("active"))
