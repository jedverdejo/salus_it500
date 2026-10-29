"""Integración Salus iT500 (nube Arrayent / app iT500 Plus)."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import ArrayentClient
from .const import CONF_API_KEY, CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import Salusit500Coordinator

PLATFORMS = ["climate", "switch", "number"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura la integración desde una entrada de configuración."""
    data = entry.data
    if not data.get(CONF_API_KEY):
        # Entrada creada con la versión antigua (portal salus-it500.com):
        # pide la apikey y vuelve a descubrir el dispositivo.
        raise ConfigEntryAuthFailed("Falta la apikey de la nueva API")

    client = ArrayentClient(
        async_get_clientsession(hass),
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_API_KEY],
        data.get(CONF_DEVICE_ID),
    )
    coordinator = Salusit500Coordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga la integración."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
