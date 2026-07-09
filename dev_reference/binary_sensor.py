### Descartado -> Ya hace la misma funcion hvac_action de climate

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from .const import DOMAIN
from .salus_api import SalusAPI, STR_STATUS

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SalusHeatingStatusSensor(coordinator, zone=1, name="Salus Heating1"),
        SalusHeatingStatusSensor(coordinator, zone=2, name="Salus Heating2"),
        
    ]
    async_add_entities(entities)

class SalusHeatingStatusSensor(BinarySensorEntity):
    def __init__(self, coordinator, zone, name):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Zone {zone} Heating Status"
        self._attr_unique_id = f"{coordinator.api._id}_zone_{zone}_heating"
        self.zone = zone
        self._name = name

    @property
    def state(self):
        return self.coordinator.api.data.get(f"CH{self.zone}{STR_STATUS}")
