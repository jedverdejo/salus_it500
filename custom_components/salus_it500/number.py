"""Number platform for Salus integration (frost temperature)."""

import logging
from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from .const import DOMAIN, MIN_TEMP, MAX_TEMP
from .salus_api import STR_FROSTT


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Salus Number platform from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SalusFrostNumber(coordinator)
    ]
    async_add_entities(entities)

class SalusFrostNumber(NumberEntity):
    """Expose frost temperature as a number entity."""
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "ºC"

    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_native_step = 0.5
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Frost temp"
        self._attr_unique_id = f"{coordinator.api._id}_frost_temp"

    @property
    def native_value(self) -> float | None:
        return float(self.coordinator.api.data.get(f"{STR_FROSTT}"))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_frost(value)
        await self.coordinator.async_request_refresh()

