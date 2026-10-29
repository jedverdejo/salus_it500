import asyncio
import sys
import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from homeassistant.components.climate import HVACAction, HVACMode  # noqa: E402

from custom_components.salus_it500 import config_flow, number, switch  # noqa: E402,F401
from custom_components.salus_it500.client import Mode  # noqa: E402
from custom_components.salus_it500.climate import Salusit500Climate  # noqa: E402
from custom_components.salus_it500.switch import SalusMasterSwitch  # noqa: E402


def coord(data):
    m = MagicMock()
    m.data = data
    m.last_update_success = True
    m.async_set_mode = AsyncMock()
    m.async_set_setpoint = AsyncMock()
    return m


def mk(data, zone=1):
    return Salusit500Climate(coord(data), "uid", "T", zone, f"Z{zone}")


def test_climate_off():
    e = mk({"A84": "1910", "A85": "2000", "A89": "1"})
    assert e.hvac_mode == HVACMode.OFF and e.target_temperature is None
    assert e.current_temperature == 19.1 and e.hvac_action == HVACAction.OFF


def test_climate_auto_hold_and_manual():
    assert mk({"A84": "2000", "A88": "1"}).hvac_mode == HVACMode.AUTO
    assert mk({"A84": "2000", "A92": "1", "A87": "1"}).hvac_action == HVACAction.HEATING


def test_climate_actions():
    e = mk({"A84": "2000"})
    asyncio.run(e.async_set_hvac_mode(HVACMode.HEAT))
    e.coordinator.async_set_mode.assert_awaited_with(1, Mode.MANUAL)
    asyncio.run(e.async_set_temperature(temperature=21.5))
    e.coordinator.async_set_setpoint.assert_awaited_with(1, 21.5)


def test_master_switch():
    s = SalusMasterSwitch(coord({"A84": "1", "B84": "1", "A89": "1", "B89": "1"}), "u", "T")
    assert s.is_on is False
    s = SalusMasterSwitch(coord({"A84": "1", "B84": "1", "A89": "1"}), "u", "T")
    assert s.is_on is True
    asyncio.run(s.async_turn_off())
    assert s.coordinator.async_set_mode.await_count == 2
