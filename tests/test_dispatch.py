from common.commands import Command
from common.errors import ErrorCode
from common.menu import MASTER_MENU, REMOTE_MENU, Menu
from common.protocol import Frame, RemoteLink, decode_frames, encode_frame
from common.state import LinkState, commit
from remote.atu_link import TestMode
from remote.button_emulation import Fallback, OptoBank
from remote.tasks import PowerView, apply_menu, dispatch_frame


class _Latch:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.writes: list[int] = []

    def write(self, value: int) -> None:
        self.writes.append(value)
        self.value = value

    def read(self) -> int:
        return self.value


class _Port:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)


def _frame(command: Command, sequence: int = 1) -> bytes:
    return encode_frame(Frame(1, 2, sequence, command, b""))


def _world(mode: str = "serial", antenna: int = 1, power: float = 0.2):
    link = RemoteLink()
    link.execute_tuner = True
    latch = _Latch(0 if antenna == 0 else 1 << (antenna - 1))
    state = LinkState()
    commit(state, antenna=antenna, relay_mask=latch.value)
    commit(state, antenna=antenna, relay_mask=latch.value)
    return {
        "link": link,
        "latch": latch,
        "state": state,
        "power": PowerView(power, 0, 0),
        "port": _Port(),
        "mode": mode,
        "test_mode": TestMode(),
        "fallback": Fallback(),
        "opto": OptoBank(),
    }


def _run(command: Command, mode: str = "serial", antenna: int = 1, power: float = 0.2):
    world = _world(mode, antenna, power)
    seen = []
    original = world["link"].finish

    def finish(action):
        seen.append(("finish", world["latch"].writes[:], world["state"].antenna))
        return original(action)

    world["link"].finish = finish
    reply = dispatch_frame(_frame(command), **world)
    frames, _leftover = decode_frames(reply)
    return world, frames[0], seen


def test_at2_below_threshold_acks_after_the_latch():
    world, frame, seen = _run(Command.AT2, antenna=1, power=0.2)
    assert seen[0][0] == "finish"
    assert 0b0010 in seen[0][1]
    assert seen[0][2] == 2
    assert world["latch"].read() == 0b0010
    assert frame.command is Command.ACK
    assert frame.payload == bytes([0x12])


def test_at2_above_threshold_is_hot_switch():
    world, frame, _seen = _run(Command.AT2, antenna=1, power=5.0)
    assert frame.command is Command.ERR
    assert frame.payload == bytes([6, 2, 0x12])
    assert world["latch"].writes == []


def test_at0_below_threshold_opens_every_coil():
    world, frame, _seen = _run(Command.AT0, antenna=2, power=0.2)
    assert world["latch"].read() == 0
    assert frame.payload == bytes([0x10])


def test_f86_opens_coils_at_50_w():
    world, frame, _seen = _run(Command.F86, antenna=2, power=50.0)
    assert world["latch"].read() == 0
    assert world["state"].antenna == 0
    assert world["state"].relay_mask == 0
    assert world["state"].previous.antenna == 2
    assert b'{"Reset":true}\n' not in b"".join(world["port"].writes)
    assert frame.payload == bytes([0x35])


def test_rst_opens_coils_and_resets_the_tuner():
    world, frame, _seen = _run(Command.RST, antenna=2, power=50.0)
    assert world["state"].antenna == 0
    assert world["state"].relay_mask == 0
    assert world["latch"].read() == 0
    assert world["state"].previous.antenna == 2
    assert b'{"Reset":true}\n' in b"".join(world["port"].writes)
    assert frame.payload == bytes([0x33])


def _serial(command: Command, line: bytes | None, ack: int, mode: TestMode | None = None):
    world = _world()
    if mode is not None:
        world["test_mode"] = mode
    reply = dispatch_frame(_frame(command), **world)
    frame = decode_frames(reply)[0][0]
    assert frame.command is Command.ACK
    assert frame.payload == bytes([ack])
    if line is None:
        assert world["port"].writes == []
    else:
        assert world["port"].writes == [line]
    return world


def test_serial_byp0():
    _serial(Command.BYP0, b'{"Bypass":false}\n', 0x21)


def test_serial_byp1():
    _serial(Command.BYP1, b'{"Bypass":true}\n', 0x22)


def test_serial_am0():
    _serial(Command.AM0, b'{"Auto":true}\n', 0x23)


def test_serial_am1():
    _serial(Command.AM1, b'{"Auto":false}\n', 0x24)


def test_serial_tun():
    _serial(Command.TUN, b'{"Tune":true}\n', 0x20)


def test_serial_sta():
    _serial(Command.STA, b'{"Status":true}\n', 0x04)


def test_serial_tup():
    _serial(Command.TUP, b'{"RelayI":1}\n', 0x27)


def test_serial_tdn():
    _serial(Command.TDN, b'{"RelayI":0}\n', 0x28)


def test_serial_tsc():
    _serial(Command.TSC, b'{"RelayC":128}\n', 0x29)


def test_serial_tsl():
    _serial(Command.TSL, b'{"RelayI":0}\n', 0x2A)


def test_serial_tst1():
    world = _serial(Command.TST1, None, 0x26)
    assert world["test_mode"].active is True


def test_serial_tst0():
    mode = TestMode()
    mode.command(Command.TST1)
    world = _serial(Command.TST0, b'{"Reset":true}\n', 0x25, mode)
    assert world["test_mode"].active is False


def _fallback(command: Command):
    world = _world(mode="fallback")
    reply = dispatch_frame(_frame(command), **world)
    frame = decode_frames(reply)[0][0]
    return world, frame


def test_fallback_tune_presses_and_writes_nothing():
    world, frame = _fallback(Command.TUN)
    assert world["opto"].pressed == [("tune", 400)]
    assert world["port"].writes == []
    assert frame.command is Command.ACK


def test_fallback_byp0():
    world, frame = _fallback(Command.BYP0)
    assert world["port"].writes == []
    assert frame.payload == bytes([Command.BYP0.byte])


def test_fallback_byp1():
    world, frame = _fallback(Command.BYP1)
    assert world["opto"].pressed == [("bypass", 80)]
    assert world["port"].writes == []
    assert frame.payload == bytes([0x22])


def test_fallback_am0():
    world, frame = _fallback(Command.AM0)
    assert world["opto"].pressed == [("auto", 80)]
    assert frame.payload == bytes([0x23])


def test_fallback_am1():
    world, frame = _fallback(Command.AM1)
    assert world["port"].writes == []
    assert frame.payload == bytes([0x24])


def test_fallback_tup_is_data_not_available():
    for command in (Command.TUP, Command.TDN, Command.TSC, Command.TSL, Command.TST0, Command.TST1, Command.STA):
        world, frame = _fallback(command)
        assert frame.command is Command.ERR
        assert frame.payload[0] == ErrorCode.DATA_NOT_AVAILABLE
        assert world["port"].writes == []
        assert world["opto"].pressed == []


def test_master_menu_tune_enqueues_tun():
    from master.tasks import enqueue_menu

    menu = Menu(MASTER_MENU)
    menu.open_menu()
    menu.down()
    menu.right()
    assert menu.label == "Tune"
    queue = []
    enqueue_menu(menu, queue)
    assert queue == [Command.TUN]


def test_remote_menu_at4_with_link_down():
    menu = Menu(REMOTE_MENU, link_up=False)
    menu.open_menu()
    menu.right()
    menu.down()
    menu.down()
    menu.down()
    latch = _Latch(0)
    state = LinkState(antenna=0)
    tx = bytearray()
    apply_menu(menu.select(), latch, state, PowerView(0.0, 0, 0), link_up=False, tx=tx)
    assert latch.read() == 0b1000
    assert tx == b""
