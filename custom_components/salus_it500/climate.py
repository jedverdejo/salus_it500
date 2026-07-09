import logging
import asyncio
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate.const import (
    HVACMode, 
    ClimateEntityFeature, 
    HVACAction,
    
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)

from .const import DOMAIN
from .const import (
    MODE_OFF, 
    MODE_AUTO, 
    MODE_MANUAL, 
    MAX_TEMP, 
    MIN_TEMP,
    SCHEDULE_DAYS, 
    SCHEDULE_SERVICE,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configuración de las entidades climate."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Creamos dos entidades, una para cada zona
    entities = [
        Salusit500Climate(coordinator, zone=1, name="Salus Zona 1"),
        Salusit500Climate(coordinator, zone=2, name="Salus Zona 2")
    ]
    async_add_entities(entities)
       

class Salusit500Climate(CoordinatorEntity, ClimateEntity):
    """Representación de una zona de Salus it500."""

    _attr_icon = "mdi:thermostat"

    def __init__(self, coordinator, zone, name):
        """Inicialización de la entidad."""
        super().__init__(coordinator) # Esto es importante si usas CoordinatorEntity
        self.coordinator = coordinator
        self._zone = zone
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.api._id}_zone_{zone}"
       
        # Características soportadas
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        # HEAT no se expone: la API no distingue de forma fiable manual/auto
        # (ver TODO en salus_api.hvac_mode), así que solo ofrecemos OFF/AUTO.
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
        self._attr_temperature_unit = "°C"
        self._attr_min_temp = MIN_TEMP
        self._attr_max_temp = MAX_TEMP
        
        # Valores por defecto iniciales para evitar errores de None
        self._attr_hvac_mode = HVACMode.OFF 
        self._attr_target_temperature = 20.0
        self._attr_current_temperature = 20.0
        
    @property
    def should_poll(self):
        return False  # El coordinador se encarga del polling

    @property
    def min_temp(self):
        return MIN_TEMP

    @property
    def max_temp(self):
        return MAX_TEMP

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def current_temperature(self):
        # Usamos los datos cacheados en el coordinador
        return self.coordinator.api.current_temperature(self._zone)

    @property
    def target_temperature(self):
        return self.coordinator.api.target_temperature(self._zone)

    async def async_set_temperature(self, **kwargs):
        """Cambiar la temperatura objetivo."""
        temp = kwargs.get("temperature")
        if temp is not None:
            await self.coordinator.api.set_temperature(temp, self._zone)
            # set_temperature ya actualiza el caché local (coordinator.api.data),
            # así que podemos reflejar el cambio en la UI al instante sin
            # esperar a una nueva consulta al servidor de Salus (lento).
            self.async_write_ha_state()
            # Confirmamos el estado real con el servidor en segundo plano,
            # sin bloquear la respuesta al usuario.
            self.hass.async_create_task(self._delayed_refresh())

    @property
    def hvac_mode(self):
        """Retorna el modo actual (MANUAL, AUTO o OFF)."""
        
        mode = self.coordinator.api.hvac_mode(self._zone)
          
        if mode == MODE_AUTO:
            return HVACMode.AUTO
        elif mode == MODE_MANUAL:
            return HVACMode.HEAT
        else:
            return HVACMode.OFF
      
    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Establece el modo de funcionamiento (Heat/Off)."""
        _LOGGER.info(f"Cambiando modo zona {self._zone} a {hvac_mode}")
        
        if hvac_mode == HVACMode.OFF:
            # Enviamos el comando de apagado a la API
            await self.coordinator.api.set_hvac_mode(MODE_OFF, self._zone)
            optimistic_auto_off = "1"
        elif hvac_mode == HVACMode.HEAT:
            # En Salus, "Heat" suele corresponder al modo Auto o Manual
            await self.coordinator.api.set_hvac_mode(MODE_AUTO, self._zone)
            optimistic_auto_off = "0"
        else:
           await self.coordinator.api.set_hvac_mode(MODE_AUTO, self._zone)
           optimistic_auto_off = "0"

        # A diferencia de set_temperature, set_hvac_mode no actualiza el
        # caché local por sí solo: lo hacemos aquí para que la UI refleje
        # el cambio al instante en lugar de esperar al servidor de Salus.
        self.coordinator.api.data[f"CH{self._zone}autoOff"] = optimistic_auto_off
        self.async_write_ha_state()
        self.hass.async_create_task(self._delayed_refresh())

    async def _delayed_refresh(self):
        """Confirma el estado real con el servidor de Salus sin bloquear la UI."""
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
    
    @property
    def hvac_action(self):
        if self.coordinator.api.hvac_action(self._zone):
            return(HVACAction.HEATING)
        else:
            return(HVACAction.IDLE)
