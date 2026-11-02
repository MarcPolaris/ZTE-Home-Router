"""Switch platform for ZTE Router."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_MUMIMO
from .coordinator import ZTEDataUpdateCoordinator
from .entity import ZTEEntity, build_device_info, dig
from .zte_client import ZTECommandError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ZTESwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[dict[str, Any]], bool] = lambda data: False
    turn_on_fn: str = ""
    turn_off_fn: str = ""
    available_fn: Callable[[dict[str, Any]], bool] = lambda data: True


SWITCHES: tuple[ZTESwitchDescription, ...] = (
    ZTESwitchDescription(
        key="dual_band_sync",
        translation_key="dual_band_sync",
        name="Wi-Fi 双频合一",
        icon="mdi:access-point-network",
        is_on_fn=lambda d: dig(d, "wifi", "dual_band_sync", default=False),
        turn_on_fn="main_wifi_dual_on",
        turn_off_fn="main_wifi_dual_off",
    ),
    ZTESwitchDescription(
        key="mlo",
        translation_key="mlo",
        name="Wi-Fi 频段聚合 (MLO)",
        icon="mdi:lan-connect",
        is_on_fn=lambda d: dig(d, "wifi", "mlo_enabled", default=False),
        turn_on_fn="main_wifi_mlo_on",
        turn_off_fn="main_wifi_mlo_off",
    ),
    ZTESwitchDescription(
        key="wifi_2g",
        translation_key="wifi_2g",
        name="2.4GHz Wi-Fi",
        icon="mdi:wifi",
        is_on_fn=lambda d: dig(d, "wifi", "main", "2.4ghz", "enabled", default=False),
        turn_on_fn="main_wifi_2g_on",
        turn_off_fn="main_wifi_2g_off",
    ),
    ZTESwitchDescription(
        key="hide_2g",
        translation_key="hide_2g",
        name="隐藏 2.4GHz SSID",
        icon="mdi:wifi-off",
        is_on_fn=lambda d: dig(d, "wifi", "main", "2.4ghz", "hidden", default=False),
        turn_on_fn="main_wifi_hide2g_on",
        turn_off_fn="main_wifi_hide2g_off",
    ),
    ZTESwitchDescription(
        key="wifi_5g",
        translation_key="wifi_5g",
        name="5GHz Wi-Fi",
        icon="mdi:wifi",
        is_on_fn=lambda d: dig(d, "wifi", "main", "5ghz", "enabled", default=False),
        turn_on_fn="main_wifi_5g_on",
        turn_off_fn="main_wifi_5g_off",
    ),
    ZTESwitchDescription(
        key="hide_5g",
        translation_key="hide_5g",
        name="隐藏 5GHz SSID",
        icon="mdi:wifi-off",
        is_on_fn=lambda d: dig(d, "wifi", "main", "5ghz", "hidden", default=False),
        turn_on_fn="main_wifi_hide5g_on",
        turn_off_fn="main_wifi_hide5g_off",
    ),
    ZTESwitchDescription(
        key="guest_wifi_2g",
        translation_key="guest_wifi_2g",
        name="访客 2.4GHz Wi-Fi",
        icon="mdi:wifi-strength-2",
        is_on_fn=lambda d: dig(d, "guest_wifi", "2.4ghz", "enabled", default=False),
        turn_on_fn="guest_2g_on",
        turn_off_fn="guest_2g_off",
    ),
    ZTESwitchDescription(
        key="guest_wifi_5g",
        translation_key="guest_wifi_5g",
        name="访客 5GHz Wi-Fi",
        icon="mdi:wifi-strength-4",
        is_on_fn=lambda d: dig(d, "guest_wifi", "5ghz", "enabled", default=False),
        turn_on_fn="guest_5g_on",
        turn_off_fn="guest_5g_off",
    ),
    ZTESwitchDescription(
        key="wifi5_compat",
        translation_key="wifi5_compat",
        name="Wi-Fi 5 兼容网络",
        icon="mdi:wifi-cog",
        is_on_fn=lambda d: dig(d, "wifi_compat", "force_wifi", default=False),
        turn_on_fn="compat_on",
        turn_off_fn="compat_off",
        available_fn=lambda d: bool(d.get("wifi_compat")),
    ),
    ZTESwitchDescription(
        key="wifi5_compat_2g",
        translation_key="wifi5_compat_2g",
        name="Wi-Fi 5 兼容网络 2.4GHz",
        icon="mdi:wifi-plus",
        # the router keeps the band Enable flags while the master switch is
        # off, but the SSIDs only broadcast when ForceWiFi is on: report the
        # effective state (master AND band) so HA never shows "on" bands
        # while the whole compat network is off
        is_on_fn=lambda d: (
            dig(d, "wifi_compat", "force_wifi", default=False)
            and dig(d, "wifi_compat", "2.4ghz", "enabled", default=False)
        ),
        turn_on_fn="compat_2g_on",
        turn_off_fn="compat_2g_off",
        available_fn=lambda d: bool(dig(d, "wifi_compat", "2.4ghz")),
    ),
    ZTESwitchDescription(
        key="wifi5_compat_5g",
        translation_key="wifi5_compat_5g",
        name="Wi-Fi 5 兼容网络 5GHz",
        icon="mdi:wifi-plus",
        is_on_fn=lambda d: (
            dig(d, "wifi_compat", "force_wifi", default=False)
            and dig(d, "wifi_compat", "5ghz", "enabled", default=False)
        ),
        turn_on_fn="compat_5g_on",
        turn_off_fn="compat_5g_off",
        available_fn=lambda d: bool(dig(d, "wifi_compat", "5ghz")),
    ),
    ZTESwitchDescription(
        key="mumimo",
        translation_key="mumimo",
        name="MU-MIMO",
        icon="mdi:radar",
        is_on_fn=lambda d: dig(d, KEY_MUMIMO, "mumimo", default=False),
        turn_on_fn="mumimo_on",
        turn_off_fn="mumimo_off",
        available_fn=lambda d: d.get(KEY_MUMIMO) is not None,
    ),
)

# maps descriptive action names to client calls
MAIN_WIFI_OVERRIDES: dict[str, dict[str, Any]] = {
    "main_wifi_dual_on": {"dual_band_sync": True},
    "main_wifi_dual_off": {"dual_band_sync": False},
    "main_wifi_mlo_on": {"mlo": True},
    "main_wifi_mlo_off": {"mlo": False},
    "main_wifi_2g_on": {"enable_2g": True},
    "main_wifi_2g_off": {"enable_2g": False},
    "main_wifi_5g_on": {"enable_5g": True},
    "main_wifi_5g_off": {"enable_5g": False},
    "main_wifi_hide2g_on": {"hide_2g": True},
    "main_wifi_hide2g_off": {"hide_2g": False},
    "main_wifi_hide5g_on": {"hide_5g": True},
    "main_wifi_hide5g_off": {"hide_5g": False},
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZTEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ZTEPauseSwitch(coordinator)]
        + [ZTESwitch(coordinator, desc) for desc in SWITCHES]
    )


class ZTEPauseSwitch(CoordinatorEntity[ZTEDataUpdateCoordinator], SwitchEntity):
    """Pause/resume polling (like zte_tracker's pause switch).

    Purely local: it never talks to the router, so it keeps working while
    polling is paused. With the switch ON the integration sends no requests
    at all, leaving the single admin session free for the router web UI or
    the ZTE mobile app. Every other entity freezes at its last known state.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:pause-circle"
    _attr_name = "暂停跟踪器"
    _attr_translation_key = "pause_tracker"

    def __init__(self, coordinator: ZTEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = build_device_info(coordinator)
        device = coordinator.data.get("device", {}) if coordinator.data else {}
        serial = device.get("serial_number") or coordinator.entry.data["host"]
        self._attr_unique_id = f"{serial}_pause_tracker"
        self._attr_is_on = coordinator.paused

    @property
    def suggested_object_id(self) -> str | None:
        """Stable, language independent entity_id (switch.pause_tracker)."""
        return "pause_tracker"

    @property
    def available(self) -> bool:
        """Always available: the switch itself needs no router round-trip."""
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.coordinator.paused
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.pause()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.resume()
        self._attr_is_on = False
        self.async_write_ha_state()


class ZTESwitch(ZTEEntity, SwitchEntity):
    """Representation of a ZTE router switch."""

    entity_description: ZTESwitchDescription

    def __init__(
        self,
        coordinator: ZTEDataUpdateCoordinator,
        description: ZTESwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id_base}_{description.key}"
        self._optimistic: bool | None = None
        self._optimistic_deadline = 0.0

    @property
    def suggested_object_id(self) -> str | None:
        """Stable, language independent entity_id (e.g. sensor.wan_ip)."""
        return self.entity_description.key

    @property
    def is_on(self) -> bool:
        if self._optimistic is not None:
            return self._optimistic
        return self.entity_description.is_on_fn(self.coordinator.data)

    def _handle_coordinator_update(self) -> None:
        """Drop the optimistic value once the router reports the new state."""
        if self._optimistic is not None:
            actual = self.entity_description.is_on_fn(self.coordinator.data or {})
            if actual == self._optimistic or time.monotonic() >= self._optimistic_deadline:
                self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.entity_description.available_fn(
            self.coordinator.data
        )

    async def _apply(self, action: str) -> None:
        from functools import partial

        client = self.coordinator.client
        data = self.coordinator.data
        try:
            if action.startswith("main_wifi"):
                await self.hass.async_add_executor_job(
                    partial(client.set_main_wifi, **MAIN_WIFI_OVERRIDES[action])
                )
            elif action.startswith("guest_"):
                cur_2g = dig(data, "guest_wifi", "2.4ghz", "enabled", default=False)
                cur_5g = dig(data, "guest_wifi", "5ghz", "enabled", default=False)
                enable_2g, enable_5g = cur_2g, cur_5g
                if action == "guest_2g_on":
                    enable_2g = True
                elif action == "guest_2g_off":
                    enable_2g = False
                elif action == "guest_5g_on":
                    enable_5g = True
                elif action == "guest_5g_off":
                    enable_5g = False
                await self.hass.async_add_executor_job(
                    partial(client.set_guest_wifi, enable_2g, enable_5g)
                )
            elif action == "compat_on":
                await self.hass.async_add_executor_job(client.set_wifi_compat, True)
            elif action == "compat_off":
                await self.hass.async_add_executor_job(client.set_wifi_compat, False)
            elif action == "compat_2g_on":
                await self.hass.async_add_executor_job(
                    partial(client.set_wifi_compat, enable_2g=True)
                )
            elif action == "compat_2g_off":
                await self.hass.async_add_executor_job(
                    partial(client.set_wifi_compat, enable_2g=False)
                )
            elif action == "compat_5g_on":
                await self.hass.async_add_executor_job(
                    partial(client.set_wifi_compat, enable_5g=True)
                )
            elif action == "compat_5g_off":
                await self.hass.async_add_executor_job(
                    partial(client.set_wifi_compat, enable_5g=False)
                )
            elif action == "mumimo_on":
                await self.hass.async_add_executor_job(client.set_mumimo, True)
            elif action == "mumimo_off":
                await self.hass.async_add_executor_job(client.set_mumimo, False)
        except ZTECommandError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run(self.entity_description.turn_on_fn, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self.entity_description.turn_off_fn, False)

    async def _run(self, action: str, target: bool) -> None:
        """Show the new state immediately, then apply it on the router."""
        self._optimistic = target
        self._optimistic_deadline = time.monotonic() + 15
        self.async_write_ha_state()
        try:
            await self._apply(action)
        except Exception:
            self._optimistic = None
            self.async_write_ha_state()
            raise
