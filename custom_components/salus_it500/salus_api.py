"""
Adds support for the Salus Thermostat units.
"""
"""
    API en desarrollo
    20260310
    Tomado de it500-new y actualizando con la librería pyit500-main

    Voy a implementar únicamente los canales para heating (ignoro hotwater)
    Tampoco voy a procesar el schedule, aunque se guarde en formato raw la respuesta y podría procesarse
    
    NO CONSIGO AVERIGUAR CÓMO PONER MODO MANUAL
    
    Voy a adaptar la libreria para usar aiohttp en lugar de requests
"""
import asyncio
import aiohttp
import logging
import re
import time
import json
from typing import Any
from .exceptions import (IT500AuthenticationError, IT500CommandError, IT500ConnectionError, IT500InvalidParameter)
from .const import MODE_OFF, MODE_AUTO, MODE_MANUAL, MAX_TEMP, MIN_TEMP, SCHEDULE_DAYS, SCHEDULE_SERVICE 

_LOGGER = logging.getLogger(__name__)

__version__ = "0.0.2"

# API base URLs

BASE_URL = "https://salus-it500.com/"
URL_LOGIN = f"{BASE_URL}public/login.php"
URL_GET_TOKEN = f"{BASE_URL}public/control.php"
URL_GET_DATA = f"{BASE_URL}public/ajax_device_values.php"
URL_SET_DATA = f"{BASE_URL}includes/set.php"
URL_ONLINE_STATUS = f"{BASE_URL}public/ajax_device_online_status.php"
URL_DEVICES = f"{BASE_URL}public/devices.php"
URL_LOGOUT = f"{BASE_URL}includes/logout.php"
URL_SESSION_REFRESH = f"{BASE_URL}ajax_session_update.php"
URL_PROGRAM= f"{BASE_URL}program.php"
URL_BATTERY_CHECK = f"{BASE_URL}ota/battery_check.php"
URL_OTA_LAPIS = f"{BASE_URL}ota/poll_lapis_version.php"
URL_OTA_CC1110 = f"{BASE_URL}ota/poll_cc1110_version.php"
URL_CHANGE_PASSWORD = f"{BASE_URL}public/reset.php?remoteApp="

# Responses' keywords
LOGIN_PAGE_TEXT = "loginRegister"
INVALID_LOGIN_TEXT = "Invalid login name or password"
INVALID_EMAIL_TEXT = "Please enter a valid email address."

# Parameters

DEFAULT_NAME = "Salus it500"
IT500_ZONES = 2
SALUS_TIMEOUT_SEC = 10
LOW_BATTERY = 0
# ENUM OTA_NEEDED {"none", "lapis", "cc1110", "both"
# ONLINE_STATUS = { "online", "online lowBat", "online lowBat2", "offline" }

# Variables names in responses

STR_CURRENT_TEMP = "currentRoomTemp"
STR_TARGET_TEMP = "currentSetPoint"
STR_AUTOFF = "autoOff"
STR_MANUAL = "manual"
STR_SCHED = "schedType"
STR_STATUS = "heatOnOffStatus"
STR_AUTOMODE = "autoMode"
STR_HEAT = "heatOnOff"
STR_FROSTSTATUS = "frostActive"
STR_FROSTT = "frost"

# Significado
#
# heatOnOffStatus -> Estado actual de la bomba (encendido/apagado) 1 ON / 0 OFF
# autoOff -> 1 si termostato apagado / 0 termostato activo
# manual -> Modo manual activado (parece que sólo si temperatura fijada a mano)
# schedType -> ¿? Parece estar siempre a 0
# autoMode -> 1 si se ha forzado temperatura : Parece que sólo para que se reactive cuando llegue el siguiente evento
# heatOnOff -> 1 si termostato apagado

## Defines tomados de otra versión (PENDIENTE DE COMPROBAR SI SIRVEN PARA ALGO)

# Supported climate features
SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_FAN_MODE = 8
SUPPORT_PRESET_MODE = 16

# HVAC modes
HVAC_MODE_OFF = "off"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_COOL = "cool"
HVAC_MODE_AUTO = "auto"

# HVAC states
CURRENT_HVAC_OFF = "off"
CURRENT_HVAC_HEAT = "heating"
CURRENT_HVAC_HEAT_IDLE = "heating (idling)"
CURRENT_HVAC_COOL = "cooling"
CURRENT_HVAC_COOL_IDLE = "cooling (idling)"
CURRENT_HVAC_IDLE = "idle"

# Supported presets
PRESET_FOLLOW_SCHEDULE = "Follow Schedule"
PRESET_PERMANENT_HOLD = "Permanent Hold"
PRESET_TEMPORARY_HOLD = "Temporary Hold"
PRESET_ECO = "Eco"
PRESET_OFF = "Off"

# SalusError se mantiene como alias de IT500Error por compatibilidad con el
# resto del módulo, que originalmente definía su propia excepción genérica.
SalusError = IT500Error

class SalusAPI:
    def __init__(self, name, username, password, sid, session: aiohttp.ClientSession):
        """Device init."""
        self.version = __version__
        self.zones = IT500_ZONES
        self.name = name
        self._username = username
        self._password = password
        self._id = sid
        self._session = session  # Recibimos la sesión de aiohttp
        
        self.token = None
        self.data: dict[str, Any] = {}
        self.battery_ota: dict[str, Any] = {}
        self.battery: str = None
        self.ota: str = None
        
        # Estas dos no las usa geminai
#        self.dev_name: str = None
#        self.dev_status: str = None
        
        _LOGGER.info(f"SALUS API: Initialized for {name}")
#        print("[SALUS API] Inicializado (vacio)")

    async def initialize(self):
        """Inicialización asíncrona de datos."""
#        print("[SALUS API] Inicializando datos")
        _LOGGER.info("[SALUS API] Initializing data from device")
        try:
            self.token = await self._get_token()                                       
            await self.update()
            _LOGGER.info("[SALUS API]: Initialization success")
            await self.ota_ver()
            await self.battery_check()
            
        except Exception as e:
            _LOGGER.error(f"[SALUS API]: Initialization error: {e}")

    # --- Métodos de consulta de datos locales (Síncronos porque no tocan red) ---
    
    def current_temperature(self, zone):
        campo = f"CH{zone}{STR_CURRENT_TEMP}"
        return float(self.data.get(campo, 0))

    def target_temperature(self, zone):
        campo = f"CH{zone}{STR_TARGET_TEMP}"
        return float(self.data.get(campo, 0))
        
#    def frost_temp(self):
#        campo = f"{STR_FROSTT}"
#        return float(self.data.get(campo,0))

    def hvac_mode(self, zone):
        """Return the current HVAC mode (OFF/MANUAL/AUTO)"""
        """ Difference among MANUAL/AUTO is soft (void)"""

        campo = f"CH{zone}{STR_AUTOFF}"
#        if zone == 1:
#            print(f"[SALUS API] Obteniendo modo hvac para zone {zone}")
#            print(f"CH1autoOff:{self.data["CH1autoOff"]}, CH1manual: {self.data["CH1manual"]}, CH1heatOnOffStatus: {self.data["CH1heatOnOffStatus"]}, CH1autoMode: {self.data["CH1autoMode"]}, CH1heatOnOff: {self.data["CH1heatOnOff"]}, CH1schedType: {self.data["CH1schedType"]}")
        if zone == 1 or zone == 2:
          try:
            """Returns the mode based on API flags."""
            auto_off = int(self.data.get(f"CH{zone}{STR_AUTOFF}", 0))
            is_manual = int(self.data.get(f"CH{zone}{STR_MANUAL}", 0))
            is_auto = int(self.data.get(f"CH{zone}{STR_AUTOMODE}", 0))

            if auto_off == 1:
                return MODE_OFF
            # TODO: no se ha conseguido determinar cómo distingue la API el modo
            # MANUAL del AUTO a partir de "manual"/"autoMode". De momento se
            # devuelve siempre MODE_AUTO cuando el termostato no está apagado.
            return MODE_AUTO
          except Exception:
            return None        
        else:
            _LOGGER.info(f"SALUS API: Error zona leyendo hvac_mode")
 
    def hvac_action(self, zone):
        """Return the current state of heater (ON/OFF - CHxheatOnOffStatus) - Heating/Not heating"""
        """Returns 1 for Heating, 0 for Idle."""
        return int(self.data.get(f"CH{zone}{STR_STATUS}", 0))
        
    def frost_temp(self):
        campo = "frost"
        return float(self.data.get(campo, 0))
    
  
    # --- Métodos de Red (Asíncronos) ---

    async def online(self):
        if self.token is None:
            return False
        
        try:
            async with self._session.get(URL_ONLINE_STATUS, timeout=SALUS_TIMEOUT_SEC) as r:
                text = await r.text()
                if (text == '"online"' or text == '"online lowBat"'):
                    return text
                else:
                    return "offline"
        except Exception as e:
            _LOGGER.error(f"Error checking online status: {e}")
            return False

    async def set_temperature(self, temperature, zone):
        if str(zone) not in ["1", "2"]:
            _LOGGER.info("SALUS API: Error in zone id")
            raise SalusError("Error in zone id")

        if not (MIN_TEMP <= float(temperature) <= MAX_TEMP):
            raise IT500InvalidParameter(f"Temperature not valid {temperature}")

        payload = {
            "token": self.token, 
            "devId": self._id, 
            "tempUnit": "0", 
            f"current_tempZ{zone}_set": "1", 
            f"current_tempZ{zone}": str(temperature)
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
#        print(f"Set temperature payload {payload}")

        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as resp:
                if resp.status == 200:
                    _LOGGER.info("SALUS API: Salus set_temperature OK")
                    # Optimistic update
                    self.data[f"CH{zone}{STR_TARGET_TEMP}"] = temperature
                else:
                    raise IT500CommandError(f"SALUS API set_temperature HTTP Error {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Error Setting the temperature: {e}")
            raise SalusError("SALUS API: Error setting temperature")

    async def set_hvac_mode(self, hvac_mode, zone):
        # Modes AUTO/MANUAL are equal - No difference currently
        # auto 1 es OFF y auto 0 es ON
        # auto_setZN es siempre 1
    
        if self.token is None:
            await self._get_token()

        if str(zone) not in ["1", "2"]:
            _LOGGER.info("SALUS API: Error in zone id")
            raise SalusError("Error in zone id")
            
        if hvac_mode not in [MODE_OFF, MODE_MANUAL, MODE_AUTO]:
            _LOGGER.info("SALUS API: Error in mode for zone {zone}")
            raise SalusError("Error in set_hvac_mode")
           
        if hvac_mode == MODE_OFF:
            mode = "1"
            clave = "1"
        elif hvac_mode == MODE_AUTO:
            mode = "0"
            clave = "1"
        else:
            clave = "1"
            mode = "1"
          
        payload = {
            "token": self.token, 
            "devId": self._id, 
            "auto": mode,
            f"auto_setZ{zone}": clave, 
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
#        print(f"Set hvac_mode payload {payload}")

        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as resp:
                if resp.status == 200:
                    _LOGGER.info("SALUS API: Salus set_hvac_mode OK")
                else:
                    raise IT500CommandError(f"SALUS API set_hvac_mode HTTP Error {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Error Setting the mode: {e}")
            raise SalusError("SALUS API: Error setting mode")

    async def async_set_frost(self, frost: float, zone) -> None:
        if self.token is None:
            await self._get_token()

        payload = {
            "token": self.token,
            "devId": self._id,
            "tempUnit": "0",
            "frost_temp_set": zone,
            "frost_temp": frost,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
 
        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as resp:
                if resp.status == 200:
                    _LOGGER.info("SALUS API: Salus set_frost OK")
                else:
                    raise IT500CommandError(f"SALUS API set_frost HTTP Error {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Error Setting frost: {e}")
            raise SalusError("SALUS API: Error setting frost")

    async def set_hvac_mode_man(self, hvac_mode, zone):
        # Modes AUTO/MANUAL are equal - No difference currently

        if str(zone) not in ["1", "2"]:
            _LOGGER.info("SALUS API: Error in zone id")
            raise SalusError("Error in zone id")
            
        if hvac_mode not in [MODE_OFF, MODE_MANUAL, MODE_AUTO]:
            _LOGGER.info("SALUS API: Error in mode for zone {zone}")
            raise SalusError("Error in set_hvac_mode")
           
        if hvac_mode == MODE_OFF:
            mode = "1"
        elif hvac_mode == MODE_AUTO:
            mode = "0"
        else:
            mode = "0"
          
        payload = {
            "token": self.token, 
            "devId": self._id, 
            "manual": zone,
            f"manual_setZ{zone}": mode, 
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
#        print(f"Set hvac_mode payload {payload}")

        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as resp:
                if resp.status == 200:
                    _LOGGER.info("SALUS API: Salus set_hvac_mode OK")
                else:
                    raise IT500CommandError(f"SALUS API set_hvac_mode HTTP Error {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Error Setting the mode: {e}")
            raise SalusError("SALUS API: Error setting mode")        

    async def _get_token(self):
        payload = {"IDemail": self._username, "password": self._password, "login": "Login"}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            # Step 1: Login to establish session
            async with self._session.post(URL_LOGIN, data=payload, headers=headers) as resp:
                content = await resp.text()
                if INVALID_LOGIN_TEXT in content or INVALID_EMAIL_TEXT in content:
                    raise IT500AuthenticationError("SALUS API Authentication failed")

            # Step 2: Get the control page to scrape the token
            params = {"devId": self._id}
            async with self._session.get(URL_GET_TOKEN, params=params) as resp_token:
                token_content = await resp_token.text()
                result = re.search('<input id="token" type="hidden" value="(.*)" />', token_content)
                if result:
                    self.token = result.group(1)
                    _LOGGER.info(f"SALUS API: Token acquired: {self.token}")
                    return self.token
                raise IT500ConnectionError("Token not found in response")
        except IT500AuthenticationError:
            # Re-lanzamos tal cual para que el llamante distinga credenciales
            # inválidas de un problema de conectividad.
            raise
        except Exception as e:
            _LOGGER.error(f"SALUS API: Error login - {e}")
            raise IT500ConnectionError("Error Getting the Session Token") from e

    async def _get_data(self, retry=True):
        if not self.token:
            await self._get_token()

        params = {
            "devId": self._id, 
            "token": self.token, 
            "&_": str(int(time.time() * 1000))
        }

        try:
            async with self._session.get(URL_GET_DATA, params=params, timeout=SALUS_TIMEOUT_SEC) as r:
                if r.status == 200:
                    # text = await r.text()
                    # self.data = json.loads(text)
                    self.data = await r.json(content_type=None) # Handles text/json variations
                    return self.data
#                    print("[SALUS API] Salusfy get_data zone output "+self.token+" DATA: "+self.data["CH1currentRoomTemp"]+","+self.data["CH1currentSetPoint"]+", "+self.data["CH1autoOff"] +", "+self.data["CH1manual"])
                elif r.status == 401 and retry:
                    _LOGGER.warning("Token expired, retrying...")
                    await self._get_token()
                    return await self._get_data(retry=False)
                else:
                    # Si falla, intentamos renovar token una vez
#                    print("[SALUS API] No se pudo leer datos")
                    raise SalusError(f"API returned status {r.status}")
                    # await self._get_token()
                    # Reintento recursivo simple
                    # return await self._get_data()
        except Exception as e:
            _LOGGER.error(f"SALUS API: Error getting data: {e}")
            raise SalusError("Error connection to salus-it500.com")

    async def update(self):
        """Actualiza los datos de la API."""
        await self._get_data()

    async def logout(self):
        if self.token:
            params = {"devId": self._id, "token": self.token, "&_": str(int(time.time() * 1000))}
            try:
                async with self._session.get(URL_LOGOUT, params=params) as r:
                    _LOGGER.info("SALUS API: Logged out")
                    self.token = None
            except:
                _LOGGER.warning("SALUS API: Error during logout")

    # Funciones auxiliares del dispositivo

    async def get_devices(self):
        if self.token is None: await self._get_token()
        params = {"devId": self._id, "token": self.token, "&_": str(int(time.time() * 1000))}
        async with self._session.get(URL_DEVICES, params=params) as r:
            text = await r.text()
            cadena = f'<div class="deviceList {self._id}"><a class="deviceIcon (.*)" href="control.php\\?devId={self._id}">(.*)</a>'
            result = re.search(cadena, text)
            if result:
                self.dev_name = result.group(2)
                return self.dev_name

    async def battery_check(self):
        if self.token is None: await self._get_token()
        params = {"devId": self._id, "token": self.token, "&_": str(int(time.time() * 1000))}
        async with self._session.get(URL_BATTERY_CHECK, params=params) as r:
            self.battery = await r.text()
            return self.battery

    async def ota_ver(self):
        if self.token is None: await self._get_token()
        params = {"devId": self._id, "token": self.token, "&_": str(int(time.time() * 1000))}
        async with self._session.get(URL_OTA_LAPIS, params=params) as r:
            self.ota = await r.text()
            return self.ota
            
