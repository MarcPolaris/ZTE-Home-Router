"""Data update coordinator for ZTE Router."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FULL_INTERVAL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_FULL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_DEVICE,
    KEY_LAN_DEVICES,
)
from .zte_client import ZTEAuthError, ZTECommandError, ZTEConnectionError, ZTERouterClient

_LOGGER = logging.getLogger(__name__)


class ZTEDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the router and expose the aggregated state.

    Polling runs in two tiers: the fast endpoints (WiFi/WAN/MU-MIMO) every
    few seconds, the slow ones (device info, LAN devices, mesh topology) every
    ``SLOW_REFRESH_EVERY`` cycles.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ZTERouterClient) -> None:
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry
        self._cycle = 0
        full_interval = entry.options.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)
        self._slow_every = max(1, round(full_interval / max(1, scan_interval)))

    @property
    def device_name(self) -> str:
        """Device name, overridable from the options flow."""
        custom = (self.entry.options.get(CONF_NAME) or "").strip()
        if custom:
            return custom
        model = self.device_info_state.get("model") or "ZTE Router"
        return f"{model} ({self.entry.data[CONF_HOST]})"

    def _is_slow_cycle(self) -> bool:
        """True when the device/LAN/topology endpoints should be refreshed."""
        if self.data is None:
            return True
        self._cycle += 1
        return self._cycle % self._slow_every == 0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if self._is_slow_cycle():
                # merge instead of replace: a full poll that skips (or fails on)
                # one endpoint must not wipe that key, otherwise every entity
                # bound to it flashes "unavailable" until the next fast poll
                slow = await self.hass.async_add_executor_job(self.client.poll_all)
                data = dict(self.data or {})
                data.update(slow)
                return data
            fast = await self.hass.async_add_executor_job(self.client.poll_fast)
            data = dict(self.data or {})
            data.update(fast)
            return data
        except ZTEAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except (ZTEConnectionError, ZTECommandError) as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err

    @property
    def device_info_state(self) -> dict[str, Any]:
        return self.data.get(KEY_DEVICE, {}) if self.data else {}

    @property
    def lan_devices(self) -> list[dict[str, Any]]:
        return (self.data or {}).get(KEY_LAN_DEVICES, []) or []

    # ------------------------------------------------------------------
    # pause / resume polling (mirrors zte_tracker's pause switch)
    # ------------------------------------------------------------------
    @property
    def paused(self) -> bool:
        """True while scheduled polling is suspended."""
        return self.update_interval is None

    def pause(self) -> None:
        """Suspend all scheduled polling.

        While paused the integration generates zero traffic to the router so
        the user can manage the web UI (or the mobile app) without the
        integration fighting over the single admin session. Entities keep
        showing their last known state.
        """
        self._unschedule_refresh()
        self.update_interval = None
        _LOGGER.info("Polling paused for %s", self.name)

    def resume(self) -> None:
        """Restart scheduled polling with the configured intervals."""
        scan_interval = self.entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._cycle = 0
        self.update_interval = timedelta(seconds=scan_interval)
        self.hass.async_create_task(self.async_request_refresh())
        _LOGGER.info("Polling resumed for %s", self.name)
