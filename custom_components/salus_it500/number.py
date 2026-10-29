"""Temperatura antihielo (S09), en centésimas de grado."""
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.exceptions import HomeAssistantError

from .client import ATTR_FROST, ArrayentError
from .const import DOMAIN
from .entity import SalusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if ATTR_FROST in coordinator.data:
        uid = entry.unique_id or entry.entry_id
        async_add_entities([SalusFrostNumber(coordinator, uid, entry.title)])


class SalusFrostNumber(SalusEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_native_min_value = 4
    _attr_native_max_value = 17
    _attr_native_step = 0.5
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator, uid, title):
        super().__init__(coordinator, uid, title)
        self._attr_name = f"{title} Frost temp"
        self._attr_unique_id = f"{uid}_frost_temp"

    def _raw(self):
        try:
            return float(self.coordinator.data.get(ATTR_FROST))
        except (TypeError, ValueError):
            return None

    @property
    def native_value(self):
        raw = self._raw()
        if raw is None:
            return None
        # Formato sin confirmar: centésimas (≥100) o grados directos.
        return raw / 100 if raw >= 100 else raw

    async def async_set_native_value(self, value: float) -> None:
        centi = (self._raw() or 500) >= 100
        try:
            await self.coordinator.client.set_frost(value, centi=centi)
        except ArrayentError as err:
            raise HomeAssistantError(f"Salus no aplicó el cambio: {err}") from err
        await self.coordinator.async_request_refresh()
