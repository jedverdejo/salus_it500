import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import DOMAIN
from .salus_api import SalusAPI
from .exceptions import IT500AuthenticationError, IT500ConnectionError

DATA_SCHEMA = vol.Schema({
    vol.Required("name", default="Mi Salus"): str,
    vol.Required("username"): str,
    vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    vol.Required("id"): str,
})


class Salusit500ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestión del flujo de configuración."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Evita añadir dos veces el mismo termostato (mismo devId)
            await self.async_set_unique_id(user_input["id"])
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = SalusAPI(
                user_input["name"],
                user_input["username"],
                user_input["password"],
                user_input["id"],
                session,
            )
            try:
                await api._get_token()
            except IT500AuthenticationError:
                errors["base"] = "invalid_auth"
            except IT500ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input["name"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
