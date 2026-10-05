# Master Pico entry. Flash this file to /main.py along with the common and master packages.
# The master has no relay coils. Boot only starts the watchdog.
# The repeating task list is started from boot_devices.

from common import hal
from common.hal import note_rx_byte
from common.mcp23017 import MCP23017, OlatView
from common.scheduler import run_once
from common.ssd1306 import SSD1306
from master import config
from master.tasks import MasterApp, build_master_tasks


def boot_master(events: list[str]) -> None:
    """Start the watchdog. This board does not touch a relay."""
    hal.start_watchdog(config.WATCHDOG_MS)
    events.append("watchdog")


def boot_devices(role: str = "master") -> MasterApp:
    """Open UART0 and I2C from config. UART1 stays closed on this board."""
    if role != "master":
        raise ValueError(role)
    app = MasterApp()
    events: list[str] = []
    boot_master(events)
    app.boot_events = events
    _open_buses(app)
    app.tasks = build_master_tasks(app)
    return app


def _open_buses(app: MasterApp) -> None:
    """UART0 is the U094. The tuner UART is reserved and not opened."""
    if hal.machine is None:
        return
    machine = hal.machine
    app.uart0 = machine.UART(
        0,
        baudrate=config.RS485_BAUD,
        tx=machine.Pin(config.RS485_TX),
        rx=machine.Pin(config.RS485_RX),
    )
    app.uart1 = None
    i2c = machine.I2C(0, scl=machine.Pin(config.I2C_SCL), sda=machine.Pin(config.I2C_SDA), freq=config.I2C_FREQ)
    app.oled = SSD1306(i2c, config.OLED_ADDR)
    app.oled.init()
    app.mcp = MCP23017(i2c, config.MCP23017_ADDR)
    app.mcp.write_iodir(0xFF, 0x83)
    app.mcp.write_pullups(0xFF, 0x03)
    app.mcp.enable_interrupts()
    app.olat = OlatView(app.mcp, "master")
    _arm_uart(app.uart0, app.rs485, app.rs485_flags)
    _arm_pin(machine.Pin(config.MCP_INTA), app.mcp_flag)
    _arm_pin(machine.Pin(config.MCP_INTB), app.mcp_flag)


def _arm_uart(uart: object, ring: object, flags: object) -> None:
    """The UART interrupt only stores bytes. Decoding waits for the task pass."""

    def _on_rx(source: object) -> None:
        """Store every waiting byte. Decoding waits for the task pass."""
        while source.any():
            data = source.read(1)
            if not data:
                break
            note_rx_byte(ring, flags, data[0])

    if hal.machine is None or not hasattr(uart, "irq"):
        return
    uart.irq(_on_rx, hal.machine.UART.IRQ_RXIDLE)


def _arm_pin(pin: object, flags: object) -> None:
    """INTA and INTB only raise a flag. The pass reads the expander."""

    def _on_edge(_pin: object) -> None:
        """Raise the expander flag. The task pass reads the GPIO registers."""
        flags.mcp = True

    if hasattr(pin, "irq"):
        pin.irq(_on_edge)


def _interrupt(app: MasterApp) -> None:
    """Read the expander once the pin interrupt has raised the flag."""
    if not app.mcp_flag.mcp:
        return
    if getattr(app, "mcp", None) is not None:
        app.mcp.read_gpio()
    app.mcp_flag.mcp = False


def run_production_pass(board: MasterApp) -> None:
    """Read the clock once, then run the task list. Tests that set now_ms call run_once."""
    board.now_ms = hal.ticks_ms()
    run_once(board.tasks, interrupt=lambda: _interrupt(board), watchdog=hal.feed_watchdog)


if __name__ == "__main__":
    board = boot_devices("master")
    while True:
        run_production_pass(board)
