"""Number platform for Salus integration (frost temperature)."""

import asyncio
import logging
from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MIN_TEMP, MAX_TEMP
from .salus_api import STR_FROSTT


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Salus Number platform from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SalusFrostNumber(coordinator)
    ]
    async_add_entities(entities)

class SalusFrostNumber(CoordinatorEntity, NumberEntity):
    """Expose frost temperature as a number entity."""
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "ºC"

    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_native_step = 0.5
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Frost temp"
        self._attr_unique_id = f"{coordinator.api._id}_frost_temp"

    @property
    def native_value(self) -> float | None:
        return float(self.coordinator.api.data.get(f"{STR_FROSTT}"))

    async def async_set_native_value(self, value: float) -> None:
        # NOTA: la API pide una "zona" aunque el valor de antihielo parece
        # ser único para todo el dispositivo. Se usa zona 1 por defecto;
        # revisa que el comportamiento sea el esperado en tu termostato.
        await self.coordinator.api.async_set_frost(value, 1)
        self.coordinator.api.data[STR_FROSTT] = value
        self.async_write_ha_state()
        self.hass.async_create_task(self._delayed_refresh())

    async def _delayed_refresh(self):
        """Confirma el estado real con el servidor de Salus sin bloquear la UI."""
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

