from common.commands import Command
from common.display import Reading, screen_lines
from common.protocol import MasterLink, RemoteLink
from common.state import LinkState
from master.tasks import drain_rs485 as master_drain
from master.tasks import maybe_poll
from remote.atu_link import AtuLink, TestMode
from remote.button_emulation import Fallback, OptoBank
from remote.tasks import PowerView
from remote.tasks import drain_rs485 as remote_drain
from remote.tasks import poll_atu, publish_display


class _Latch:
    def __init__(self) -> None:
        self.value = 0
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


class _Panel:
    def __init__(self) -> None:
        self.lines = None

    def show_lines(self, lines: tuple[str, str, str, str]) -> None:
        self.lines = lines


_STATUS = (
    "{\n"
    '  "Auto": true,\n'
    '  "Bypass": false,\n'
    '  "efficency": 90,\n'
    '  "Power": 9.0,\n'
    '  "Forward": 10.0,\n'
    '  "SWR": 1.10,\n'
    '  "Order": "LC"\n'
    "}\n"
).encode()


class Exchange:
    """One master, one remote, and a fake tuner, joined by bytearrays."""

    def __init__(self) -> None:
        self.master = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
        self.remote = RemoteLink()
        self.to_remote = bytearray()
        self.to_master = bytearray()
        self.latch = _Latch()
        self.remote_state = LinkState()
        self.master_state = LinkState()
        self.port = _Port()
        self.atu = AtuLink(self.port)
        self.test_mode = TestMode()
        self.fallback = Fallback()
        self.opto = OptoBank()
        self.panel = _Panel()
        self.power = PowerView(0.0, 0, 0)

    def enqueue(self, command: Command) -> None:
        self.master.enqueue(command)

    def feed_atu(self, data: bytes) -> None:
        self.atu.feed(data)

    def step(self, now_ms: int) -> None:
        """Move one poll and the replies it causes. No sockets and no sleep."""
        self.power = PowerView(0.0, now_ms, now_ms)
        poll_atu(self.atu, self.remote_state, self.remote, now_ms)
        maybe_poll(self.master, now_ms, self.to_remote)
        for _ in range(8):
            if self.to_remote:
                reply = remote_drain(
                    self.remote,
                    self.to_remote,
                    self.latch,
                    self.remote_state,
                    self.power,
                    self.port,
                    self.test_mode,
                    self.fallback,
                    self.opto,
                )
                if reply:
                    self.to_master.extend(reply)
            if self.to_master:
                master_drain(self.master, self.to_master, self.master_state)
            if self.master._phase in ("saw_rs", "saw_snd"):
                maybe_poll(self.master, now_ms, self.to_remote)
            if not self.to_remote and not self.to_master and self.master._phase == "idle":
                break
        publish_display(self.master_state, self.panel)


def run_exchange() -> Exchange:
    """Build the in-process link. The test queues commands and steps the clock."""
    return Exchange()


def test_at2_then_tune_against_fake_atu():
    session = run_exchange()
    session.enqueue(Command.AT2)
    session.step(200)
    assert session.latch.read() == 0b0010
    assert "RX ACK AT2" in session.master.log
    session.enqueue(Command.TUN)
    session.step(400)
    assert b'{"Tune":true}\n' in b"".join(session.port.writes)
    session.feed_atu(_STATUS)
    session.step(600)
    state = session.master_state
    lines = screen_lines(
        Reading(
            state.forward_w,
            state.swr,
            state.inductance_nh or 0,
            state.capacitance_pf or 0,
            state.auto,
            state.bypass,
            state.order or "LC",
            state.efficiency_pct,
            state.antenna_w,
        )
    )
    assert lines == ("10.0W          .", "1.10", "9.0W", "90%")
