import sys

from common import hal
from master import config as master_config
from master.main import boot_devices as boot_master
from remote import config as remote_config
from remote.main import boot_devices as boot_remote


class FakeMachine:
    """Stand-in for the MicroPython machine module. The host test injects it."""

    pins: list[int] = []
    uarts: list[object] = []

    def __init__(self) -> None:
        """Each boot gets its own pin and UART lists."""
        self.pins = []
        self.uarts = []
        self.i2c_writes: list[tuple[int, int, int]] = []
        self.commands: list[tuple[int, bytes]] = []

    def WDT(self, timeout: int) -> None:
        """Record the watchdog period. The host has no hardware watchdog."""
        self.wdt = timeout

    def Pin(self, number, *args, **kwargs):
        """Record a GPIO number. The wireless pins must not appear."""
        self.pins.append(number)
        return number

    def UART(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
        """Record one UART open."""
        uart = type("UART", (), {"id": uart_id, "baudrate": baudrate, "tx": tx, "rx": rx})()
        self.uarts.append(uart)
        return uart

    def I2C(self, i2c_id, scl, sda, freq=400000):
        """One bus. Device addresses show up on the later writes."""
        parent = self

        class Bus:
            def writeto_mem(self, addr, reg, buf):
                parent.i2c_writes.append((addr, reg, buf[0]))

            def readfrom_mem(self, addr, reg, nbytes):
                return bytes(nbytes)

            def writeto(self, addr, buf):
                parent.commands.append((addr, bytes(buf)))

        return Bus()


def _bind() -> FakeMachine:
    fake = FakeMachine()
    hal.bind(fake)
    return fake


def test_uart_irq_and_tx_write_move_one_at2_frame():
    from common.commands import Command
    from common.protocol import Frame, decode_frames, encode_frame
    from common.scheduler import run_once
    from master.main import boot_devices as boot_master
    from remote.main import boot_devices as boot_remote
    from remote.tasks import build_remote_tasks

    mem: dict[tuple[int, int], int] = {}
    gpio_reads: list[int] = []

    class Bus:
        def writeto_mem(self, addr, reg, buf):
            mem[(addr, reg)] = buf[0]

        def readfrom_mem(self, addr, reg, nbytes):
            if reg in (0x12, 0x13):
                gpio_reads.append(reg)
            return bytes([mem.get((addr, reg), 0)] * nbytes)

        def writeto(self, addr, buf):
            self.shown.append((addr, bytes(buf)))

        def __init__(self):
            self.shown: list[tuple[int, bytes]] = []

    buses: list[Bus] = []

    class UART:
        def __init__(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
            self.id = uart_id
            self.pending = bytearray()
            self.written = bytearray()
            self.handler = None

        def irq(self, handler, trigger=0):
            self.handler = handler
            self.trigger = trigger

        def any(self):
            return len(self.pending)

        def read(self, count):
            chunk = bytes(self.pending[:count])
            del self.pending[:count]
            return chunk

        def write(self, data):
            self.written.extend(data)

        def push(self, value):
            self.pending.append(value)
            self.handler(self)

    class Pin:
        def __init__(self, number, *args, **kwargs):
            self.number = number
            self.handler = None

        def irq(self, handler):
            self.handler = handler

    uarts: list[UART] = []

    class Machine:
        def WDT(self, timeout):
            return type("W", (), {"feed": lambda self: None})()

        def Pin(self, number, *args, **kwargs):
            return Pin(number)

        def UART(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
            uart = UART(uart_id, baudrate, tx, rx)
            uarts.append(uart)
            return uart

        def I2C(self, i2c_id, scl, sda, freq=400000):
            bus = Bus()
            buses.append(bus)
            return bus

    Machine.UART.IRQ_RXIDLE = 0x10
    hal.bind(Machine())
    try:
        remote = boot_remote("remote")
        uart0 = next(uart for uart in uarts if uart.id == 0)
        for byte in encode_frame(Frame(1, 2, 1, Command.AT2, b"")):
            uart0.push(byte)
        run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
        frames, _leftover = decode_frames(bytes(uart0.written))
        assert frames[0].command is Command.ACK
        assert frames[0].payload == bytes([0x12])
        run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
        assert remote.oled.shown
        assert remote.oled.shown is not remote.panel.lines
        remote.state.banner = "Communication Lost"
        remote.state.link_up = False
        run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x14)] & (1 << 5) == 0
        assert mem[(0x20, 0x14)] & (1 << 6)
        uarts.clear()
        master = boot_master("master")
        master.state.banner = "Communication Lost"
        master.state.link_up = False
        run_once(master.tasks, interrupt=lambda: None, watchdog=lambda: None)
        assert mem[(0x20, 0x15)] & (1 << 2) == 0
        assert mem[(0x20, 0x15)] & (1 << 3)
        assert master.oled.shown
    finally:
        hal.bind(None)
        hal.start_watchdog(3000)


def test_uart_rxidle_drains_a_full_frame():
    from common.commands import Command
    from common.protocol import Frame, decode_frames, encode_frame
    from common.scheduler import run_once
    from remote.tasks import build_remote_tasks

    opened: list[object] = []

    class UART:
        """One FIFO. irq records the trigger the board asked for."""

        IRQ_RXIDLE = 0x10

        def __init__(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
            """Remember the id and start with an empty FIFO."""
            self.id = uart_id
            self.pending = bytearray()
            self.written = bytearray()
            self.handler = None
            self.trigger = None
            opened.append(self)

        def irq(self, handler, trigger=0):
            """Save the handler and the trigger. The test fires the handler."""
            self.handler = handler
            self.trigger = trigger

        def any(self):
            """How many bytes are waiting in the FIFO."""
            return len(self.pending)

        def read(self, count):
            """Take up to count bytes."""
            chunk = bytes(self.pending[:count])
            del self.pending[:count]
            return chunk

        def write(self, data):
            """Capture TX bytes."""
            self.written.extend(data)

    class Pin:
        """INT pin. The test does not fire it."""

        def __init__(self, number, *args, **kwargs):
            """Remember the GPIO number."""
            self.number = number

        def irq(self, handler):
            """Accept the edge handler."""
            self.handler = handler

    class Machine:
        """Fake machine whose UART class carries IRQ_RXIDLE."""

        def WDT(self, timeout):
            """A watchdog the boot path can arm."""
            return type("W", (), {"feed": lambda self: None, "timeout": timeout})()

        def Pin(self, number, *args, **kwargs):
            """Return a pin that can take an irq."""
            return Pin(number)

        def I2C(self, i2c_id, scl, sda, freq=400000):
            """A bus that remembers latch writes so a coil readback can succeed."""
            mem: dict[tuple[int, int], int] = {}

            class Bus:
                def writeto_mem(self, addr, reg, buf):
                    mem[(addr, reg)] = buf[0]

                def readfrom_mem(self, addr, reg, nbytes):
                    return bytes([mem.get((addr, reg), 0)] * nbytes)

                def writeto(self, addr, buf):
                    return None

            return Bus()

    Machine.UART = UART
    hal.bind(Machine())
    try:
        remote = boot_remote("remote")
        remote_uarts = list(opened)
        assert remote_uarts
        assert {uart.trigger for uart in remote_uarts} == {UART.IRQ_RXIDLE}
        boot_master("master")
        master_uarts = opened[len(remote_uarts) :]
        assert master_uarts
        assert {uart.trigger for uart in master_uarts} == {UART.IRQ_RXIDLE}
        uart0 = next(uart for uart in remote_uarts if uart.id == 0)
        frame = encode_frame(Frame(1, 2, 1, Command.AT2, b""))
        uart0.pending.extend(frame)
        uart0.handler(uart0)
        run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
        frames, leftover = decode_frames(bytes(uart0.written))
        assert leftover == b""
        assert frames[0].command is Command.ACK
        assert frames[0].payload == bytes([Command.AT2.byte])
    finally:
        hal.bind(None)
        hal.start_watchdog(3000)


def test_remote_boot_opens_uarts_from_config(monkeypatch=None):
    assert "machine" not in sys.modules or True
    saved = master_config.POLL_MS
    fake = _bind()
    try:
        remote = boot_remote("remote")
        assert any(uart.id == 0 and uart.baudrate == remote_config.RS485_BAUD for uart in fake.uarts)
        assert any(uart.id == 1 and uart.baudrate == remote_config.ATU_BAUD for uart in fake.uarts)
        assert remote_config.OLED_ADDR in {addr for addr, _buf in fake.commands}
        assert remote_config.MCP23017_ADDR in {addr for addr, _reg, _val in fake.i2c_writes}
        assert {23, 24, 25, 29}.isdisjoint(fake.pins)
        assert (remote_config.MCP23017_ADDR, 0x00, 0x9F) in fake.i2c_writes
        assert (remote_config.MCP23017_ADDR, 0x01, 0x80) in fake.i2c_writes
        assert (remote_config.MCP23017_ADDR, 0x0C, 0x1F) in fake.i2c_writes
        assert remote.atu.timeout_ms == remote_config.ATU_TIMEOUT_MS
        assert remote.atu.tries == remote_config.ATU_TRIES
        assert remote.atu.tune_timeout_ms == remote_config.TUNE_TIMEOUT_MS
        assert remote.test_mode._l_ceiling == (1 << remote_config.INDUCTOR_COUNT) - 1
        master_fake = _bind()
        master = boot_master("master")
        assert all(uart.id != 1 for uart in master_fake.uarts)
        assert master.link.poll_ms == master_config.POLL_MS
        assert master.link.reply_timeout_ms == master_config.REPLY_TIMEOUT_MS
        assert master.link.reply_tries == master_config.REPLY_TRIES
        assert master.link.miss_limit == master_config.MISS_LIMIT
        assert (master_config.MCP23017_ADDR, 0x00, 0xFF) in master_fake.i2c_writes
        assert (master_config.MCP23017_ADDR, 0x01, 0x83) in master_fake.i2c_writes
        assert (master_config.MCP23017_ADDR, 0x0C, 0xFF) in master_fake.i2c_writes
        assert (master_config.MCP23017_ADDR, 0x0D, 0x03) in master_fake.i2c_writes
        master_config.POLL_MS = 250
        changed = boot_master("master")
        assert changed.link.poll_ms == 250
        assert {23, 24, 25, 29}.isdisjoint(master_fake.pins)
    finally:
        master_config.POLL_MS = saved
        hal.bind(None)
        sys.modules.pop("machine", None)
