from common.commands import Command
from common.errors import ErrorCode
from common.protocol import Frame, RemoteLink, encode_frame
from common.state import LinkState
from remote.atu_link import TestMode
from remote.button_emulation import Fallback, OptoBank
from remote.tasks import PowerView, RemoteApp, build_remote_tasks, dispatch_frame


def _pulse(command: Command, hold_ms: int, bit: int, sequence: int = 1) -> None:
    from common.hal import note_rx_byte
    from common.scheduler import run_once

    app = RemoteApp()
    app.mode = "fallback"
    frame = encode_frame(Frame(1, 2, sequence, command, b""))
    for byte in frame:
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    app.now_ms = 0
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.opto.value & 0x70 == bit
    app.now_ms = hold_ms
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.opto.value & bit == 0


def test_tune_opto_is_high_for_400_ms():
    from common.hal import note_rx_byte
    from common.scheduler import run_once

    _pulse(Command.TUN, 400, 0x10)
    _pulse(Command.AM0, 80, 0x20, sequence=2)
    _pulse(Command.BYP1, 80, 0x40, sequence=3)
    _pulse(Command.RST, 100, 0x10, sequence=4)
    app = RemoteApp()
    app.mode = "fallback"
    frame = encode_frame(Frame(1, 2, 1, Command.AM0, b""))
    for byte in frame:
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    again = encode_frame(Frame(1, 2, 2, Command.AM0, b""))
    for byte in again:
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    before = app.opto.value
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.opto.value == before
    assert "time.sleep" not in open("remote/button_emulation.py", encoding="utf-8").read()
    serial = RemoteApp()
    serial.mode = "serial"
    held = serial.opto.value
    for byte in encode_frame(Frame(1, 2, 1, Command.TUN, b"")):
        note_rx_byte(serial.rs485, serial.rs485_flags, byte)
    run_once(build_remote_tasks(serial), interrupt=lambda: None, watchdog=lambda: None)
    assert serial.port_writes == [b'{"Tune":true}\n']
    assert serial.opto.value & 0x70 == held & 0x70


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
