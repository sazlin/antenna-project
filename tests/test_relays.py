import pytest

from common.errors import ErrorCode, RelayFault
from common.state import LinkState
from remote.relays import apply_antenna_command, set_antenna


class FakeLatch:
    """Latch that remembers every write and reads back the last one."""

    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.writes: list[int] = []

    def write(self, value: int) -> None:
        self.writes.append(value)
        self.value = value

    def read(self) -> int:
        return self.value


class MismatchLatch(FakeLatch):
    """Reads the target bit back as two bits so the coil check must open everything."""

    def read(self) -> int:
        if self.writes and self.writes[-1] == 0b0001:
            return 0b0011
        return self.value


def _change(latch: FakeLatch, state: LinkState, **kwargs: object) -> ErrorCode | None:
    values = {
        "now_ms": 0,
        "forward_w": 0.0,
        "sample_ms": 0,
        "threshold_w": 1.0,
        "enabled": True,
        "stale_ms": 1000,
        "delay_ms": 100,
        "sleep": lambda _ms: None,
    }
    values.update(kwargs)
    return apply_antenna_command(latch, state, **values)


def test_one_watt_is_allowed():
    state = LinkState(antenna=1)
    latch = FakeLatch(0b0001)
    assert _change(latch, state, target=2, forward_w=1.0, sample_ms=0, now_ms=0) is None
    assert latch.read() == 0b0010


def test_disabled_interlock_allows_high_power():
    state = LinkState(antenna=1)
    latch = FakeLatch(0b0001)
    result = _change(latch, state, target=3, forward_w=50.0, enabled=False, sample_ms=0, now_ms=0)
    assert result is None
    assert latch.read() == 0b0100


def test_stale_power_does_not_block():
    state = LinkState(antenna=1)
    latch = FakeLatch(0b0001)
    result = _change(
        latch,
        state,
        target=4,
        forward_w=25.0,
        sample_ms=0,
        now_ms=1000,
        stale_ms=1000,
    )
    assert result is None
    assert latch.read() == 0b1000


def test_missing_power_does_not_block():
    state = LinkState(antenna=1)
    latch = FakeLatch(0b0001)
    result = _change(latch, state, target=2, forward_w=None, enabled=True, sample_ms=10, now_ms=10)
    assert result is None
    assert latch.read() == 0b0010


def test_power_above_one_watt_blocks_antenna_change():
    state = LinkState(antenna=1)
    latch = FakeLatch(0b0001)
    for target in (2, 0):
        result = apply_antenna_command(
            latch,
            state,
            target=target,
            now_ms=500,
            forward_w=1.1,
            sample_ms=0,
            threshold_w=1.0,
            enabled=True,
            stale_ms=1000,
            delay_ms=100,
            sleep=lambda _ms: None,
        )
        assert result is ErrorCode.HOT_SWITCH
        assert latch.writes == []


def test_same_antenna_does_not_cycle():
    state = LinkState(antenna=2)
    latch = FakeLatch(0b0010)
    slept: list[int] = []
    result = apply_antenna_command(
        latch,
        state,
        target=2,
        now_ms=0,
        forward_w=0.0,
        sample_ms=0,
        threshold_w=1.0,
        enabled=True,
        stale_ms=1000,
        delay_ms=100,
        sleep=slept.append,
    )
    assert result is None
    assert latch.writes == []
    assert slept == []


def test_readback_mismatch_forces_off():
    latch = MismatchLatch(0)
    with pytest.raises(RelayFault):
        set_antenna(latch, 1, delay_ms=100, sleep=lambda _ms: None)
    assert latch.writes[-1] == 0


def test_two_bits_already_set_forces_off():
    latch = FakeLatch(0b0101)
    slept: list[int] = []
    with pytest.raises(RelayFault):
        set_antenna(latch, 3, delay_ms=100, sleep=slept.append)
    assert latch.writes[-1] == 0
    assert slept == []


def test_set_antenna_one_coil_after_all_off():
    latch = FakeLatch(0)
    slept: list[int] = []

    def sleeper(delay_ms: int) -> None:
        slept.append(delay_ms)

    set_antenna(latch, 0, delay_ms=100, sleep=sleeper)
    assert latch.writes == [0]
    assert slept == [100]
    latch = FakeLatch(0)
    slept.clear()
    set_antenna(latch, 2, delay_ms=100, sleep=sleeper)
    assert latch.writes == [0, 0b0010]
    assert slept == [100]
    assert latch.read() == 0b0010
    assert all(bin(value).count("1") <= 1 for value in latch.writes)
