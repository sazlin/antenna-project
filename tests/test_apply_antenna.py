from pathlib import Path

from common.commands import Command
from common.errors import ErrorCode, RelayFault
from common.protocol import Action
from common.state import LinkState, commit
from remote.tasks import PowerView, apply_from_link


class _Latch:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.writes: list[int] = []

    def write(self, value: int) -> None:
        self.writes.append(value)
        self.value = value

    def read(self) -> int:
        return self.value


class _Mismatch(_Latch):
    def read(self) -> int:
        if self.writes and self.writes[-1] != 0:
            return 0b0011
        if not self.writes:
            return self.value
        return 0


def test_at2_commits_after_the_coil_moves():
    state = LinkState(antenna=1, relay_mask=0b0001)
    latch = _Latch(0b0001)
    reply = apply_from_link(Action(Command.AT2, 2), latch, state, PowerView(0.2, 0, 0))
    assert latch.read() == 0b0010
    assert state.antenna == 2
    assert state.previous.antenna == 1
    assert reply.kind == "ack"


def test_hot_switch_does_not_commit():
    state = LinkState(antenna=2, relay_mask=0b0010)
    latch = _Latch(0b0010)
    reply = apply_from_link(Action(Command.AT1, 1), latch, state, PowerView(5.0, 0, 100))
    assert reply.kind == "err"
    assert reply.code is ErrorCode.HOT_SWITCH
    assert latch.read() == 0b0010
    assert latch.writes == []
    assert state.antenna == 2


def test_relay_fault_rolls_back_and_opens_every_coil():
    state = LinkState()
    commit(state, antenna=1, relay_mask=0b0001)
    commit(state, antenna=1, relay_mask=0b0001)
    latch = _Mismatch(0b0001)
    reply = apply_from_link(Action(Command.AT2, 2), latch, state, PowerView(0.2, 0, 0))
    assert reply.kind == "err"
    assert reply.code is ErrorCode.RELAY_FAULT
    assert not isinstance(reply, RelayFault)
    assert latch.read() == 0
    assert state.antenna == 0
    assert state.relay_mask == 0
    assert state.previous.antenna == 1
    assert 0b0001 not in latch.writes


def test_relay_fault_class_lives_in_errors():
    found = []
    for root in ("common", "master", "remote"):
        for path in Path(root).rglob("*.py"):
            if "class RelayFault" in path.read_text(encoding="utf-8"):
                found.append(path.as_posix())
    assert found == ["common/errors.py"]
