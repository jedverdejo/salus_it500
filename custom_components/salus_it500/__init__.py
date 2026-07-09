from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .salus_api import SalusAPI
from .coordinator import Salusit500Coordinator

# Lista de plataformas a cargar (climate, number, switch)
# No incluyo sensor ni binary_sensor por inutiles
PLATFORMS = ["climate", "switch", "number", ]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura Salus desde una entrada de configuración (IU)."""
    session = async_get_clientsession(hass) # HA gestiona esta sesión por ti
    
    api = SalusAPI(
        entry.data["name"],
        entry.data["username"],
        entry.data["password"],
        entry.data["id"],
        session
    )
    
    coordinator = Salusit500Coordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Registrar las plataformas
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
    
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga la integración (cuando el usuario la borra)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

    