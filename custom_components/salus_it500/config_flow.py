"""Flujo de configuración (alta y reautenticación)."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import ArrayentAuthError, ArrayentClient, ArrayentConnectionError, ArrayentError
from .const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _schema(defaults=None):
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "Mi Salus")): str,
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): _SECRET,
            vol.Required(CONF_API_KEY): _SECRET,
        }
    )


class Salusit500ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._input = {}
        self._devices = []
        self._reauth_entry = None

    async def _login_and_list(self, data):
        client = ArrayentClient(
            async_get_clientsession(self.hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_API_KEY],
        )
        return await client.get_devices()

    @staticmethod
    def _error(err):
        if isinstance(err, ArrayentAuthError):
            return "invalid_auth"
        if isinstance(err, ArrayentConnectionError):
            return "cannot_connect"
        return "unknown"

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                devices = await self._login_and_list(user_input)
                if not devices:
                    errors["base"] = "no_devices"
            except ArrayentError as err:
                errors["base"] = self._error(err)
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            if not errors:
                self._input = user_input
                self._devices = devices
                if len(devices) == 1:
                    return await self._create(devices[0]["devId"])
                return await self.async_step_device()
        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=errors)

    async def async_step_device(self, user_input=None):
        if user_input is not None:
            return await self._create(user_input[CONF_DEVICE_ID])
        options = [
            {"value": d["devId"], "label": d.get("devName") or d["devId"]} for d in self._devices
        ]
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): SelectSelector(SelectSelectorConfig(options=options))}),
        )

    async def _create(self, dev_id):
        await self.async_set_unique_id(dev_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._input[CONF_NAME], data={**self._input, CONF_DEVICE_ID: dev_id}
        )

    # --- Reautenticación (también sirve para migrar entradas del portal antiguo)
    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._reauth_entry
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                devices = await self._login_and_list(data)
                if not devices:
                    errors["base"] = "no_devices"
            except ArrayentError as err:
                errors["base"] = self._error(err)
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            if not errors:
                data[CONF_DEVICE_ID] = data.get(CONF_DEVICE_ID) or devices[0]["devId"]
                data.pop("id", None)  # id del portal antiguo
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD): _SECRET,
                    vol.Required(CONF_API_KEY): _SECRET,
                }
            ),
            errors=errors,
        )
