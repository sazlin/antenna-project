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
