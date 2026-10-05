from common.commands import Command
from common.errors import ErrorCode
from common.protocol import Frame, RemoteLink, encode_frame
from common.state import LinkState
from remote.atu_link import TestMode
from remote.button_emulation import Fallback, OptoBank
from remote.tasks import PowerView, dispatch_frame


def test_tune_opto_is_high_for_400_ms():
    opto = OptoBank()
    box = Fallback()
    opto.drive(box.press_for(Command.TUN), 0)
    assert opto.value & 0x70 == 0x10
    opto.service_optos(400)
    assert opto.value & 0x10 == 0
    opto.drive(box.press_for(Command.AM0), 0)
    assert opto.value & 0x70 == 0x20
    opto.service_optos(80)
    assert opto.value & 0x20 == 0
    opto.drive(box.press_for(Command.BYP1), 0)
    assert opto.value & 0x70 == 0x40
    opto.service_optos(80)
    assert opto.value & 0x40 == 0
    opto.drive(box.press_for(Command.RST), 0)
    assert opto.value & 0x10
    opto.service_optos(100)
    assert opto.value & 0x10 == 0
    before = opto.value
    opto.drive(box.press_for(Command.AM0), 0)
    assert opto.value == before
    assert "time.sleep" not in open("remote/button_emulation.py", encoding="utf-8").read()
    serial = OptoBank()
    before = serial.value

    class _Port:
        def __init__(self) -> None:
            self.writes: list[bytes] = []

        def write(self, data: bytes) -> None:
            self.writes.append(data)

    port = _Port()
    link = RemoteLink()
    dispatch_frame(
        encode_frame(Frame(1, 2, 1, Command.TUN, b"")),
        link=link,
        latch=type("L", (), {"read": lambda self: 0, "write": lambda self, _v: None})(),
        state=LinkState(),
        power=PowerView(0.0, 0, 0),
        port=port,
        mode="serial",
        test_mode=TestMode(),
        fallback=Fallback(),
        opto=serial,
    )
    assert port.writes == [b'{"Tune":true}\n']
    assert serial.value & 0x70 == before & 0x70


def test_tune_holds_400_ms():
    box = Fallback(initial_auto=False, initial_bypass=False)
    assert box.press_for(Command.TUN) == [("tune", 400)]


def test_reset_holds_tune_100_ms():
    box = Fallback()
    assert box.press_for(Command.RST) == [("tune", 100)]


def test_auto_press_toggles_once():
    box = Fallback()
    assert box.press_for(Command.AM0) == [("auto", 80)]
    assert box.auto is True
    assert box.press_for(Command.AM0) == []
    assert box.press_for(Command.AM1) == [("auto", 80)]
    assert box.auto is False


def test_bypass_press_turns_on():
    box = Fallback()
    assert box.press_for(Command.BYP1) == [("bypass", 80)]
    assert box.bypass is True


def test_direct_steps_are_data_not_available():
    box = Fallback()
    for command in (Command.TUP, Command.TDN, Command.TSC, Command.TSL, Command.TST0, Command.TST1):
        assert box.press_for(command) is ErrorCode.DATA_NOT_AVAILABLE


def test_status_is_data_not_available_in_fallback():
    box = Fallback()
    assert box.press_for(Command.STA) is ErrorCode.DATA_NOT_AVAILABLE
