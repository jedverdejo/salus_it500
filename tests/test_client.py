import asyncio
import hashlib
import importlib.util
import pathlib
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "client", pathlib.Path(__file__).parent.parent / "custom_components/salus_it500/client.py"
)
c = importlib.util.module_from_spec(spec)
sys.modules["client"] = c
spec.loader.exec_module(c)

LOGIN_OK = "<userLoginResponse><userId>U1</userId><securityToken>TOK</securityToken></userLoginResponse>"
FAULT = "<requestFault><errorCode>101</errorCode><errorMsg>bad</errorMsg></requestFault>"
DEVS = "<r><devList><devId>D1</devId><devName>x</devName></devList></r>"


def attrs_xml(d):
    return "<r>" + "".join(
        f"<attrList><name>{k}</name><value>{v}</value></attrList>" for k, v in d.items()
    ) + "</r>"


class FakeResp:
    def __init__(self, status, text):
        self.status, self._t = status, text

    async def text(self):
        return self._t

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeSession:
    """Simula la nube: aplica las escrituras a un dict."""

    def __init__(self, attrs, fail_login=False, expire_once=False):
        self.attrs = dict(attrs)
        self.calls = []
        self.fail_login = fail_login
        self.expire_once = expire_once
        self.ignore = set()

    def request(self, method, url, **kw):
        ep = url.rsplit("/", 1)[-1]
        p = kw.get("params", {})
        self.calls.append((method, ep, dict(p), kw.get("data")))
        if ep == "userLogin":
            return FakeResp(500, FAULT) if self.fail_login else FakeResp(200, LOGIN_OK)
        if self.expire_once:
            self.expire_once = False
            return FakeResp(500, FAULT)
        if ep == "getDeviceList":
            return FakeResp(200, DEVS)
        if ep == "getDeviceAttributesWithValues":
            return FakeResp(200, attrs_xml(self.attrs))
        if ep == "setMultiDeviceAttributes2":
            if p["name1"] not in self.ignore:
                self.attrs[p["name1"]] = p["value1"]
            return FakeResp(200, "<ok/>")
        return FakeResp(404, "")


def mk(session, **kw):
    return c.ArrayentClient(session, " User@X.com ", "pässword", "KEY", poll_interval=0, poll_attempts=3, **kw)


def run(coro):
    return asyncio.run(coro)


BASE = {"A84": "2150", "A85": "2000", "A87": "1", "A88": "0", "A89": "0", "A92": "0"}


def test_login_sends_md5_and_lowercase_email():
    s = FakeSession(BASE)
    run(mk(s).login())
    _, ep, params, data = s.calls[0]
    assert ep == "userLogin" and params == {"apikey": "KEY"}
    assert data["name"] == "user@x.com"
    assert data["password"] == hashlib.md5("pässword".encode()).hexdigest()
    assert data["appId"] == "1097"


def test_login_failure():
    with pytest.raises(c.ArrayentAuthError):
        run(mk(FakeSession(BASE, fail_login=True)).login())


def test_discover_and_attributes():
    cl = mk(FakeSession(BASE))
    attrs = run(cl.get_attributes())
    assert cl.dev_id == "D1" and attrs["A84"] == "2150"


def test_relogin_on_expired_token():
    s = FakeSession(BASE, expire_once=True)
    cl = mk(s, dev_id="D1")
    run(cl.get_attributes())
    assert [x[1] for x in s.calls].count("userLogin") == 2


@pytest.mark.parametrize(
    "a,mode",
    [
        ({}, c.Mode.AUTO),
        ({"A88": "1"}, c.Mode.HOLD),
        ({"A89": "1"}, c.Mode.OFF),
        ({"A89": "1", "A92": "1"}, c.Mode.MANUAL),
        ({"A92": "1", "A88": "1"}, c.Mode.MANUAL),
    ],
)
def test_decode(a, mode):
    assert c.decode_mode(a) == mode


def test_zone_state_off_has_no_target_and_no_heating():
    st = c.zone_state({"A89": "1", "A85": "2000", "A87": "1", "A84": "2100"})
    assert st.target_temp is None and not st.heating and st.current_temp == 21.0


def test_no_data_temps():
    assert c.zone_state({"A84": "8000"}).current_temp is None


PLANS = [
    (c.Mode.OFF, c.Mode.AUTO, [[("A88", "0")], [("A92", "0")], [("A89", "0")]]),
    (c.Mode.MANUAL, c.Mode.AUTO, [[("A88", "0")], [("A92", "0")]]),
    (c.Mode.HOLD, c.Mode.AUTO, [[("A88", "0")]]),
    (c.Mode.OFF, c.Mode.MANUAL, [[("A92", "1")], [("A89", "0")]]),
    (c.Mode.AUTO, c.Mode.MANUAL, [[("A92", "1")]]),
    (c.Mode.MANUAL, c.Mode.OFF, [[("A89", "1")], [("A92", "0")]]),
    (c.Mode.AUTO, c.Mode.OFF, [[("A89", "1")]]),
]


@pytest.mark.parametrize("cur,tgt,plan", PLANS)
def test_plans(cur, tgt, plan):
    assert c.mode_write_plan(1, cur, tgt) == plan


def test_plan_zone2_prefix():
    assert c.mode_write_plan(2, c.Mode.AUTO, c.Mode.OFF) == [[("B89", "1")]]


def test_set_mode_end_to_end():
    s = FakeSession({**BASE, "A89": "1"})
    cl = mk(s, dev_id="D1")
    out = run(cl.set_mode(1, c.Mode.MANUAL))
    assert c.decode_mode(out) == c.Mode.MANUAL
    writes = [x[2]["name1"] + "=" + x[2]["value1"] for x in s.calls if x[1] == "setMultiDeviceAttributes2"]
    assert writes == ["A92=1", "A89=0", "F=1"]


def test_set_mode_server_ignores_command():
    s = FakeSession(BASE)
    s.ignore = {"A89"}
    with pytest.raises(c.ArrayentCommandError):
        run(mk(s, dev_id="D1").set_mode(1, c.Mode.OFF))


def test_setpoint_auto_sets_hold():
    s = FakeSession(BASE)
    out = run(mk(s, dev_id="D1").set_setpoint(1, 22.5))
    assert out["A85"] == "2250" and out["A88"] == "1"


def test_setpoint_manual_no_hold():
    s = FakeSession({**BASE, "A92": "1"})
    out = run(mk(s, dev_id="D1").set_setpoint(1, 19))
    assert out["A85"] == "1900" and out["A88"] == "0"


def test_setpoint_off_rejected():
    with pytest.raises(c.ArrayentCommandError):
        run(mk(FakeSession({**BASE, "A89": "1"}), dev_id="D1").set_setpoint(1, 20))


def test_setpoint_zone2_always_hold():
    s = FakeSession({"B85": "2000", "B88": "0", "B89": "0", "B92": "1"})
    out = run(mk(s, dev_id="D1").set_setpoint(2, 21))
    assert out["B85"] == "2100" and out["B88"] == "1"
