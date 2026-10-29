"""Coordinador de datos del Salus iT500."""
from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ArrayentAuthError, ArrayentClient, ArrayentError, Mode
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Salusit500Coordinator(DataUpdateCoordinator[dict[str, str]]):
    """Centraliza lecturas y escrituras contra la nube."""

    def __init__(self, hass, client: ArrayentClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        try:
            return await self.client.get_attributes()
        except ArrayentAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ArrayentError as err:
            raise UpdateFailed(f"Error comunicando con la nube Salus: {err}") from err

    async def _confirmed(self, coro):
        """Ejecuta una escritura y publica el estado REAL que devuelve el servidor."""
        try:
            attrs = await coro
        except ArrayentError as err:
            # El servidor puede haber ignorado la orden: refrescamos para que
            # la interfaz vuelva al estado real.
            await self.async_request_refresh()
            raise HomeAssistantError(f"Salus no aplicó el cambio: {err}") from err
        self.async_set_updated_data(attrs)

    async def async_set_mode(self, zone: int, mode: Mode) -> None:
        await self._confirmed(self.client.set_mode(zone, mode))

    async def async_set_setpoint(self, zone: int, temperature: float) -> None:
        await self._confirmed(self.client.set_setpoint(zone, temperature))
