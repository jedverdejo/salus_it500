"""Cliente asíncrono para la nube Arrayent (zamapi) usada por la app iT500 Plus.

Módulo independiente de Home Assistant (solo depende de aiohttp).
La apikey NO se incluye aquí: la aporta quien instala la integración.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://sal-emea-p01-api.arrayent.com/zdk/services/zamapi/"
APP_ID = "1097"
DEFAULT_TIMEOUT = 15

# Valores "sin dato" que devuelve el termostato (centésimas de °C)
NO_DATA_VALUES = {5000, 7000, 8000}

ATTR_REFRESH = "F"
ATTR_ONLINE = "online"
ATTR_FROST = "S09"


class ArrayentError(Exception):
    """Error genérico del cliente."""


class ArrayentAuthError(ArrayentError):
    """Credenciales (o apikey) rechazadas."""


class ArrayentConnectionError(ArrayentError):
    """No se pudo contactar con el servidor."""


class ArrayentSessionError(ArrayentError):
    """Token de sesión inválido o caducado."""


class ArrayentCommandError(ArrayentError):
    """El servidor rechazó una escritura o no la aplicó."""


class Mode(str, Enum):
    """Modo de funcionamiento de una zona."""

    OFF = "off"
    AUTO = "auto"
    HOLD = "hold"
    MANUAL = "manual"


def zone_prefix(zone: int) -> str:
    """Prefijo de atributos de la zona (1→A, 2→B)."""
    if zone == 1:
        return "A"
    if zone == 2:
        return "B"
    raise ValueError(f"Zona no válida: {zone}")


def _flag(attrs: dict[str, str], name: str) -> bool:
    return str(attrs.get(name, "0")).strip() == "1"


def decode_mode(attrs: dict[str, str], zone: int = 1) -> Mode:
    """Decodifica el modo igual que la app (manual tiene prioridad)."""
    p = zone_prefix(zone)
    if _flag(attrs, f"{p}92"):
        return Mode.MANUAL
    if _flag(attrs, f"{p}89"):
        return Mode.OFF
    if _flag(attrs, f"{p}88"):
        return Mode.HOLD
    return Mode.AUTO


def _temp(attrs: dict[str, str], name: str) -> float | None:
    raw = attrs.get(name)
    if raw is None:
        return None
    try:
        val = int(float(raw))
    except (TypeError, ValueError):
        return None
    if val in NO_DATA_VALUES:
        return None
    return val / 100


def mode_write_plan(zone: int, current: Mode, target: Mode) -> list[list[tuple[str, str]]]:
    """Grupos de escritura (en orden) para pasar de ``current`` a ``target``.

    Cada grupo se envía por separado y se espera a que tenga éxito, como la app.
    """
    p = zone_prefix(zone)
    if target == Mode.HOLD:
        raise ValueError("HOLD no se puede fijar directamente; se activa con una consigna en AUTO")
    if target == current:
        return []
    if target == Mode.AUTO:
        if current == Mode.OFF:
            return [[(f"{p}88", "0")], [(f"{p}92", "0")], [(f"{p}89", "0")]]
        if current == Mode.MANUAL:
            return [[(f"{p}88", "0")], [(f"{p}92", "0")]]
        return [[(f"{p}88", "0")]]  # HOLD → AUTO
    if target == Mode.MANUAL:
        if current == Mode.OFF:
            return [[(f"{p}92", "1")], [(f"{p}89", "0")]]
        return [[(f"{p}92", "1")]]
    if target == Mode.OFF:
        if current == Mode.MANUAL:
            return [[(f"{p}89", "1")], [(f"{p}92", "0")]]
        return [[(f"{p}89", "1")]]
    raise ValueError(f"Modo no soportado: {target}")


@dataclass
class ZoneState:
    """Estado interpretado de una zona."""

    mode: Mode
    current_temp: float | None
    target_temp: float | None
    heating: bool
    frost_active: bool


def zone_state(attrs: dict[str, str], zone: int = 1) -> ZoneState:
    p = zone_prefix(zone)
    mode = decode_mode(attrs, zone)
    target = None if mode == Mode.OFF else _temp(attrs, f"{p}85")
    return ZoneState(
        mode=mode,
        current_temp=_temp(attrs, f"{p}84"),
        target_temp=target,
        heating=mode != Mode.OFF and _flag(attrs, f"{p}87"),
        frost_active=str(attrs.get(f"{p}90", "0")).strip() not in ("0", ""),
    )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_fault(text: str) -> tuple[str | None, str | None]:
    """Extrae (errorCode, errorMsg) de un <requestFault>."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, text[:200] if text else None
    code = msg = None
    for el in root.iter():
        if _local(el.tag) == "errorCode":
            code = (el.text or "").strip()
        elif _local(el.tag) == "errorMsg":
            msg = (el.text or "").strip()
    return code, msg


def _children_text(el: ET.Element) -> dict[str, str]:
    return {_local(c.tag): (c.text or "").strip() for c in el}


def parse_login(text: str) -> tuple[str, str]:
    root = ET.fromstring(text)
    data = {k: v for k, v in _children_text(root).items()}
    if "userId" not in data or "securityToken" not in data:
        raise ArrayentAuthError("Respuesta de login inesperada")
    return data["userId"], data["securityToken"]


def parse_devices(text: str) -> list[dict[str, str]]:
    root = ET.fromstring(text)
    return [_children_text(el) for el in root.iter() if _local(el.tag) == "devList"]


def parse_attributes(text: str) -> dict[str, str]:
    root = ET.fromstring(text)
    out: dict[str, str] = {}
    for el in root.iter():
        if _local(el.tag) == "attrList":
            d = _children_text(el)
            if "name" in d:
                out[d["name"]] = d.get("value", "")
    return out


class ArrayentClient:
    """Cliente de la API zamapi de Arrayent para el iT500."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        api_key: str,
        dev_id: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = 3.0,
        poll_attempts: int = 10,
    ) -> None:
        self._session = session
        self._email = email.strip().lower()
        self._pwd_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()  # noqa: S324 - lo exige la API
        self._api_key = api_key
        self._base = base_url if base_url.endswith("/") else base_url + "/"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self.dev_id = dev_id
        self._user_id: str | None = None
        self._token: str | None = None
        self._lock = asyncio.Lock()  # una operación de escritura a la vez
        self._poll_interval = poll_interval
        self._poll_attempts = poll_attempts

    # ---------------------------------------------------------------- HTTP
    async def _http(self, method: str, endpoint: str, **kwargs: Any) -> tuple[int, str]:
        try:
            async with self._session.request(
                method, self._base + endpoint, timeout=self._timeout, **kwargs
            ) as resp:
                return resp.status, await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ArrayentConnectionError(f"Error de conexión: {type(err).__name__}") from err

    async def login(self) -> None:
        status, text = await self._http(
            "POST",
            "userLogin",
            params={"apikey": self._api_key},
            data={"name": self._email, "password": self._pwd_md5, "appId": APP_ID},
        )
        if status != 200:
            code, msg = parse_fault(text)
            raise ArrayentAuthError(f"Login rechazado (HTTP {status}, código {code})")
        try:
            self._user_id, self._token = parse_login(text)
        except ET.ParseError as err:
            raise ArrayentError("Respuesta de login no válida") from err

    async def _authed(self, endpoint: str, params: dict[str, str], *, retry: bool = True) -> str:
        if self._token is None:
            await self.login()
        full = {"secToken": self._token, **params}
        status, text = await self._http("GET", endpoint, params=full)
        if status == 200:
            return text
        code, msg = parse_fault(text)
        if retry and status in (401, 403, 500):
            # Posible token caducado: reintento una vez tras re-login.
            _LOGGER.debug("Fallo %s en %s (código %s); reintentando con nuevo login", status, endpoint, code)
            self._token = None
            await self.login()
            return await self._authed(endpoint, params, retry=False)
        if status in (401, 403):
            raise ArrayentSessionError(f"Sesión inválida (código {code})")
        raise ArrayentCommandError(f"HTTP {status} en {endpoint} (código {code}: {msg})")

    # ----------------------------------------------------------- lecturas
    async def get_devices(self) -> list[dict[str, str]]:
        if self._user_id is None or self._token is None:
            await self.login()
        text = await self._authed("getDeviceList", {"userId": self._user_id or ""})
        return parse_devices(text)

    async def discover_device(self) -> str:
        """Devuelve el devId (si hay uno solo) y lo recuerda."""
        if self.dev_id:
            return self.dev_id
        devs = await self.get_devices()
        if not devs:
            raise ArrayentError("La cuenta no tiene dispositivos")
        self.dev_id = devs[0]["devId"]
        return self.dev_id

    async def get_attributes(self) -> dict[str, str]:
        dev = await self.discover_device()
        text = await self._authed("getDeviceAttributesWithValues", {"devId": dev})
        return parse_attributes(text)

    # --------------------------------------------------------- escrituras
    async def set_attribute(self, name: str, value: str) -> None:
        dev = await self.discover_device()
        await self._authed(
            "setMultiDeviceAttributes2",
            {"devId": dev, "name1": name, "value1": str(value)},
        )

    async def _write_group(self, group: list[tuple[str, str]]) -> None:
        # Se desconoce el formato multi-atributo: de uno en uno.
        for name, value in group:
            await self.set_attribute(name, value)

    async def request_refresh(self) -> None:
        """Pide al termostato que sincronice (F=1)."""
        await self.set_attribute(ATTR_REFRESH, "1")

    async def _wait_until(self, check, attrs_hint: dict[str, str] | None = None) -> dict[str, str]:
        """Sondea hasta que ``check(attrs)`` sea cierto o se agoten los intentos."""
        attrs = attrs_hint or {}
        for _ in range(self._poll_attempts):
            attrs = await self.get_attributes()
            if check(attrs):
                return attrs
            await asyncio.sleep(self._poll_interval)
        raise ArrayentCommandError("El termostato no aplicó el cambio a tiempo")

    async def set_mode(self, zone: int, target: Mode, *, current: Mode | None = None) -> dict[str, str]:
        """Cambia el modo y espera confirmación real del servidor."""
        async with self._lock:
            attrs = await self.get_attributes()
            cur = current if current is not None else decode_mode(attrs, zone)
            plan = mode_write_plan(zone, cur, target)
            if not plan:
                return attrs
            for group in plan:
                await self._write_group(group)
            await self.request_refresh()
            return await self._wait_until(lambda a: decode_mode(a, zone) == target)

    async def set_setpoint(self, zone: int, temperature: float) -> dict[str, str]:
        """Fija la consigna (°C) y espera confirmación."""
        p = zone_prefix(zone)
        centi = int(round(temperature * 100))
        async with self._lock:
            attrs = await self.get_attributes()
            mode = decode_mode(attrs, zone)
            if mode == Mode.OFF:
                raise ArrayentCommandError("La zona está apagada; no admite consigna")
            await self.set_attribute(f"{p}85", str(centi))
            # Zona 1: en AUTO se activa hold (A88=1); zona 2 lo hace siempre (B88=1).
            if zone == 2 or mode == Mode.AUTO:
                await self.set_attribute(f"{p}88", "1")
            await self.request_refresh()
            return await self._wait_until(
                lambda a: _temp(a, f"{p}85") == round(centi / 100, 2)
            )

    async def set_frost(self, temperature: float, *, centi: bool = True) -> None:
        """EXPERIMENTAL: formato de S09 sin confirmar (centésimas o grados)."""
        value = int(round(temperature * 100)) if centi else temperature
        await self.set_attribute(ATTR_FROST, str(value))
        await self.request_refresh()
