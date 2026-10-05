import pytest

from common.errors import RelayFault
from remote.relays import set_antenna


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
