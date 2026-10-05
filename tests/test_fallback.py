from common.commands import Command
from common.errors import ErrorCode
from common.protocol import Frame, RemoteLink, encode_frame
from common.state import LinkState
from remote.atu_link import TestMode
from remote.button_emulation import Fallback, OptoBank
from remote.tasks import PowerView, RemoteApp, build_remote_tasks, dispatch_frame


def test_fallback_tune_holds_400_ms_when_the_clock_is_not_zero():
    from common.hal import note_rx_byte
    from common.mcp23017 import MCP23017, RelayLatch
    from common.scheduler import run_once

    mem: dict[tuple[int, int], int] = {}

    class Bus:
        def writeto_mem(self, addr, reg, buf):
            mem[(addr, reg)] = buf[0]

        def readfrom_mem(self, addr, reg, nbytes):
            return bytes([mem.get((addr, reg), 0)])

    def app_at(now_ms: int):
        board = RemoteApp()
        board.mode = "fallback"
        board.latch = RelayLatch(MCP23017(Bus(), 0x20))
        board.now_ms = now_ms
        return board

    def pulse(command: Command, start: int, hold: int, bit: int, sequence: int) -> None:
        board = app_at(start)
        for byte in encode_frame(Frame(1, 2, sequence, command, b"")):
            note_rx_byte(board.rs485, board.rs485_flags, byte)
        run_once(build_remote_tasks(board), interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x15)] & 0x70 == bit
        assert mem[(0x20, 0x15)] & 0x0F == 0
        board.now_ms = start + hold
        run_once(build_remote_tasks(board), interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x15)] & bit == 0

    pulse(Command.TUN, 5000, 400, 0x10, 1)
    pulse(Command.AM0, 6000, 80, 0x20, 2)
    pulse(Command.BYP1, 7000, 80, 0x40, 3)
    pulse(Command.RST, 8000, 100, 0x10, 4)
    again = app_at(9000)
    for byte in encode_frame(Frame(1, 2, 1, Command.AM0, b"")):
        note_rx_byte(again.rs485, again.rs485_flags, byte)
    run_once(build_remote_tasks(again), interrupt=lambda: None, watchdog=lambda: None)
    again.now_ms = 9080
    run_once(build_remote_tasks(again), interrupt=lambda: None, watchdog=lambda: None)
    assert mem[(0x20, 0x15)] & 0x20 == 0
    for byte in encode_frame(Frame(1, 2, 2, Command.AM0, b"")):
        note_rx_byte(again.rs485, again.rs485_flags, byte)
    run_once(build_remote_tasks(again), interrupt=lambda: None, watchdog=lambda: None)
    assert mem[(0x20, 0x15)] & 0x20 == 0
    serial = RemoteApp()
    serial.mode = "serial"
    serial.latch = RelayLatch(MCP23017(Bus(), 0x20))
    for byte in encode_frame(Frame(1, 2, 1, Command.TUN, b"")):
        note_rx_byte(serial.rs485, serial.rs485_flags, byte)
    run_once(build_remote_tasks(serial), interrupt=lambda: None, watchdog=lambda: None)
    assert serial.port_writes == [b'{"Tune":true}\n']
    assert mem.get((0x20, 0x15), 0) & 0x70 == 0


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
