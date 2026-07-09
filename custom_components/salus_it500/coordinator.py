from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN
from .salus_api import SalusAPI 

_LOGGER = logging.getLogger(__name__)

class Salusit500Coordinator(DataUpdateCoordinator):
    """Coordinador para centralizar las consultas a la API de Salus."""

    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60), # Salus es lento, no bajes de 60s
        )
        self.api = api

    async def _async_update_data(self):
        """Obtener datos de la API."""
        try:
            # Nuestra nueva función asíncrona adaptada antes
            await self.api.update()        # Datos de temperatura y estado
#            await self.api.battery_check() # Datos de batería
#            await self.api.ota_ver()       # Versión OTA


        except Exception as err:
            raise UpdateFailed(f"Error comunicando con Salus it500: {err}")
        
        return self.api.data
#        { 
#                "main": self.api.data,
#                "battery": self.api.battery_ota,
#                "version": sefl.api.ver
#                }
            