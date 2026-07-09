# Tambien lo inhabilito, no consigo encontrar la info sobre como acceder a la bateria y parece que solo devuelve 0 o 1. Por tanto, estos sensores tienen utilidad dudosa

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from .const import DOMAIN
from .salus_api import SalusAPI, STR_STATUS

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SalusBatterySensor(coordinator, zone=1, name="Salus Bat1"),
        SalusBatterySensor(coordinator, zone=2, name="Salus Bat2"),
#         SalusOnlineSensor(coordinator),
        SalusOTAVersionSensor(coordinator),
#        SalusHeatingStatusSensor(coordinator, zone=1, name="Salus Heating1"),
#        SalusHeatingStatusSensor(coordinator, zone=2, name="Salus Heating2"),
        
    ]
    async_add_entities(entities)

class SalusBatterySensor(SensorEntity):
    """Sensor de nivel de batería (basado en battery_check)."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None
#    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, zone, name):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Battery {zone}"
        self._attr_unique_id = f"{coordinator.api._id}_battery_{zone}"
        self._name = name

    @property
    def native_value(self):
        # Asumiendo que battery_check devuelve un dict con 'battery'
        # Ajusta según el JSON real de Salus
        return self.coordinator.api.battery

class SalusOnlineSensor(SensorEntity):
    """Estado de conexión del termostato."""
#    _attr_device_class = SensorDeviceClass.ENUM
#    _attr_state_class = None

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} Online"
        self._attr_unique_id = f"{coordinator.api._id}_online"

    @property
    async def native_value(self):
        return await self.coordinator.api.online() 

    @property
    async def state(self):
        return await self.coordinator.api.online()           
        
class SalusOTAVersionSensor(SensorEntity):
    """Sensor de version OTA (basado en ota_Ver)."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api.name} OTAVersion"
        self._attr_unique_id = f"{coordinator.api._id}_otaversion"

    @property
    def native_value(self):
        # Asumiendo que battery_check devuelve un dict con 'battery'
        # Ajusta según el JSON real de Salus
        return self.coordinator.api.ota

# Movido a sensor binario   (y descartado después)     
# class SalusHeatingStatusSensor(SensorEntity):
#    def __init__(self, coordinator, zone, name):
#        self.coordinator = coordinator
#        self._attr_name = f"{coordinator.api.name} Zone {zone} Heating Status"
#        self._attr_unique_id = f"{coordinator.api._id}_zone_{zone}_heating"
#        self.zone = zone
#        self._name = name

#    @property
#    def state(self):
#        if self.coordinator.api.data.get(f"CH{self.zone}{STR_STATUS}"):
#            return "heating"
#        else:
#            return "idle"
			
