from homeassistant.components.switch import SwitchEntity
import asyncio
from .const import DOMAIN, MODE_AUTO, MODE_OFF
from .salus_api import SalusAPI

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SalusMasterSwitch(coordinator)])

class SalusMasterSwitch(SwitchEntity):
    """Switch para apagar/encender todo el sistema Salus."""
    
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Master Switch"
        self._attr_unique_id = f"{coordinator.api._id}_master_switch"

    @property
    def is_on(self):
        # Está ON si alguna zona NO está en modo OFF (autoOff == 0)
        z1_off = self.coordinator.api.data.get("CH1autoOff") == "1"
        z2_off = self.coordinator.api.data.get("CH2autoOff") == "1"
        return not (z1_off and z2_off)

    async def async_turn_off(self, **kwargs):
        """Apaga ambas zonas."""
        # Necesitarás implementar un set_hvac_mode(OFF) en tu API asíncrona
        await self.coordinator.api.set_hvac_mode(MODE_OFF, 1) # MODE_OFF
        await self.coordinator.api.set_hvac_mode(MODE_OFF, 2) # MODE_OFF
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Activa el modo Auto en ambas zonas."""
        await self.coordinator.api.set_hvac_mode(MODE_AUTO, 1) # MODE_AUTO
        await self.coordinator.api.set_hvac_mode(MODE_AUTO, 2) # MODE_AUTO
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
        