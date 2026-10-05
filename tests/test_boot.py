from remote.main import boot_remote
from master.main import boot_master


class _Latch:
    def __init__(self, value: int) -> None:
        self.value = value
        self.writes: list[int] = []
        self.cleared_before: list[str] | None = None
        self.events: list[str] | None = None

    def read(self) -> int:
        return self.value

    def write(self, value: int) -> None:
        self.writes.append(value)
        self.value = value
        if value == 0 and self.cleared_before is None and self.events is not None:
            self.cleared_before = list(self.events)


def test_remote_boot_clears_relays_first():
    events: list[str] = []
    latch = _Latch(0b0100)
    latch.events = events
    boot_remote(latch, events)
    assert events == ["relays_off", "watchdog"]
    assert latch.read() == 0
    assert latch.cleared_before == []


def test_master_boot_starts_the_watchdog():
    events: list[str] = []
    boot_master(events)
    assert events == ["watchdog"]
