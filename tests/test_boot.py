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


def test_boot_clears_mcp_relay_bits_before_the_watchdog():
    from common import hal
    from common.commands import Command
    from common.hal import note_rx_byte
    from common.protocol import Frame, encode_frame
    from common.scheduler import run_once
    from remote.main import boot_devices
    from remote.tasks import build_remote_tasks

    order: list[tuple] = []
    mem = {(0x20, 0x15): 0x72}

    class Bus:
        def writeto_mem(self, addr, reg, buf):
            mem[(addr, reg)] = buf[0]
            if reg == 0x15:
                order.append(("olat", buf[0]))

        def readfrom_mem(self, addr, reg, nbytes):
            return bytes([mem.get((addr, reg), 0)])

        def writeto(self, addr, buf):
            return None

    class Machine:
        def WDT(self, timeout):
            order.append(("wdt", timeout))

        def Pin(self, number, *args, **kwargs):
            return number

        def UART(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
            return object()

        def I2C(self, i2c_id, scl, sda, freq=400000):
            return Bus()

    hal.bind(Machine())
    try:
        app = boot_devices("remote")
        assert mem[(0x20, 0x15)] & 0x0F == 0
        assert mem[(0x20, 0x15)] & 0x70 == 0x70
        assert order.index(("wdt", 3000)) > order.index(("olat", 0x70))
        for byte in encode_frame(Frame(1, 2, 1, Command.AT1, b"")):
            note_rx_byte(app.rs485, app.rs485_flags, byte)
        run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x15)] & 0x0F == 0b0001
        assert mem[(0x20, 0x15)] & 0x70 == 0x70
        for byte in encode_frame(Frame(1, 2, 2, Command.F86, b"")):
            note_rx_byte(app.rs485, app.rs485_flags, byte)
        run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x15)] & 0x0F == 0
        assert mem[(0x20, 0x15)] & 0x70 == 0x70
    finally:
        hal.bind(None)


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
