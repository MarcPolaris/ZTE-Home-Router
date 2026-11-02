"""Button platform for ZTE Router."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZTEDataUpdateCoordinator
from .entity import ZTEEntity
from .zte_client import ZTECommandError


@dataclass(frozen=True, kw_only=True)
class ZTEButtonDescription(ButtonEntityDescription):
    method: str = ""


BUTTONS: tuple[ZTEButtonDescription, ...] = (
    ZTEButtonDescription(
        key="reboot",
        translation_key="reboot",
        name="重启路由器",
        icon="mdi:restart",
        method="reboot",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZTEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ZTEButton(coordinator, desc) for desc in BUTTONS)


class ZTEButton(ZTEEntity, ButtonEntity):
    """Representation of a ZTE router button."""

    entity_description: ZTEButtonDescription

    def __init__(
        self,
        coordinator: ZTEDataUpdateCoordinator,
        description: ZTEButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id_base}_{description.key}"

    @property
    def suggested_object_id(self) -> str | None:
        """Stable, language independent entity_id (e.g. sensor.wan_ip)."""
        return self.entity_description.key

    async def async_press(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        try:
            await self.hass.async_add_executor_job(client.reboot)
        except ZTECommandError as err:
            raise HomeAssistantError(str(err)) from err
