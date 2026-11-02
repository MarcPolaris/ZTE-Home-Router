"""Config flow for ZTE Router."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_FULL_INTERVAL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_FULL_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .zte_client import ZTEAuthError, ZTEConnectionError, ZTERouterClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
        vol.Optional(CONF_NAME, default=""): str,
    }
)


async def validate_input(hass, data):
    """Validate credentials by performing a login."""
    client = ZTERouterClient(
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )
    info = await hass.async_add_executor_job(client.get_device_info)
    return {
        "serial_number": info.get("serial_number") or data[CONF_HOST],
        "model": info.get("model") or "ZTE Router",
    }


class ZTERouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZTE Router."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ZTEAuthError:
                errors["base"] = "invalid_auth"
            except ZTEConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception in config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                custom_name = (user_input.get(CONF_NAME) or "").strip()
                return self.async_create_entry(
                    title=custom_name
                    or f"{info['model']} ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZTEOptionsFlowHandler()


class ZTEOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options: device name, refresh speed."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        entry = self.config_entry
        current_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_full = entry.options.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)
        current_name = entry.options.get(CONF_NAME, "")
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=current_name): str,
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                vol.Required(CONF_FULL_INTERVAL, default=current_full): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=MAX_SCAN_INTERVAL)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
