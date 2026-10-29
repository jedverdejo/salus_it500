"""Interruptor maestro: apaga o pone en AUTO todas las zonas."""
from homeassistant.components.switch import SwitchEntity

from .client import Mode, decode_mode, zone_prefix
from .const import DOMAIN
from .entity import SalusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    uid = entry.unique_id or entry.entry_id
    async_add_entities([SalusMasterSwitch(coordinator, uid, entry.title)])


class SalusMasterSwitch(SalusEntity, SwitchEntity):
    def __init__(self, coordinator, uid, title):
        super().__init__(coordinator, uid, title)
        self._attr_name = f"{title} Master Switch"
        self._attr_unique_id = f"{uid}_master_switch"

    @property
    def _zones(self):
        return [z for z in (1, 2) if f"{zone_prefix(z)}84" in self.coordinator.data]

    @property
    def is_on(self):
        return any(decode_mode(self.coordinator.data, z) != Mode.OFF for z in self._zones)

    async def async_turn_off(self, **kwargs):
        for z in self._zones:
            await self.coordinator.async_set_mode(z, Mode.OFF)

    async def async_turn_on(self, **kwargs):
        for z in self._zones:
            await self.coordinator.async_set_mode(z, Mode.AUTO)
