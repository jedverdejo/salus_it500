"""Plataforma climate: una entidad por zona de calefacción."""
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from .client import Mode, zone_prefix, zone_state
from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .entity import SalusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    uid = entry.unique_id or entry.entry_id
    zones = [z for z in (1, 2) if f"{zone_prefix(z)}84" in coordinator.data]
    async_add_entities(
        Salusit500Climate(coordinator, uid, entry.title, z, f"Salus Zona {z}") for z in zones
    )


class Salusit500Climate(SalusEntity, ClimateEntity):
    """Zona de calefacción del iT500."""

    _attr_icon = "mdi:thermostat"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, uid, title, zone, name):
        super().__init__(coordinator, uid, title)
        self._zone = zone
        self._attr_name = name
        self._attr_unique_id = f"{uid}_zone_{zone}"

    @property
    def _state(self):
        return zone_state(self.coordinator.data, self._zone)

    @property
    def current_temperature(self):
        return self._state.current_temp

    @property
    def target_temperature(self):
        return self._state.target_temp

    @property
    def hvac_mode(self):
        mode = self._state.mode
        if mode == Mode.OFF:
            return HVACMode.OFF
        if mode == Mode.MANUAL:
            return HVACMode.HEAT
        return HVACMode.AUTO  # AUTO y HOLD

    @property
    def hvac_action(self):
        st = self._state
        if st.mode == Mode.OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if st.heating else HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        return {"hold": self._state.mode == Mode.HOLD, "frost_active": self._state.frost_active}

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is not None:
            await self.coordinator.async_set_setpoint(self._zone, float(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        target = {
            HVACMode.OFF: Mode.OFF,
            HVACMode.AUTO: Mode.AUTO,
            HVACMode.HEAT: Mode.MANUAL,
        }[hvac_mode]
        await self.coordinator.async_set_mode(self._zone, target)
