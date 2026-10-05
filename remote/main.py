# Remote Pico entry. Flash this file to /main.py along with the common and remote packages.
# Boot opens every relay before the watchdog starts, so a stuck coil cannot sit
# through a reset. The repeating task list is started from boot_devices.

from common import hal
from common.hal import note_rx_byte
from common.mcp23017 import MCP23017, OlatView, RelayLatch
from common.scheduler import run_once
from common.ssd1306 import SSD1306
from remote import config
from remote.relays import safe_off
from remote.tasks import RemoteApp, build_remote_tasks


def boot_remote(latch: object, events: list[str]) -> None:
    """Drop every coil, then start the watchdog. A reboot must not leave a coil on."""
    safe_off(latch, "boot")
    events.append("relays_off")
    hal.start_watchdog(config.WATCHDOG_MS)
    events.append("watchdog")


def boot_devices(role: str = "remote") -> RemoteApp:
    """Open the buses from config after the coils are off. Tests do not loop."""
    if role != "remote":
        raise ValueError(role)
    app = RemoteApp()
    events: list[str] = []
    _open_buses(app)
    if getattr(app, "mcp", None) is not None:
        app.latch = RelayLatch(app.mcp)
    safe_off(app.latch, "boot")
    if getattr(app, "mcp", None) is not None:
        app.olat = OlatView(app.mcp, "remote")
    events.append("relays_off")
    hal.start_watchdog(config.WATCHDOG_MS)
    events.append("watchdog")
    app.boot_events = events
    app.tasks = build_remote_tasks(app)
    return app


def _open_buses(app: RemoteApp) -> None:
    """UART0 is the U094. UART1 is the tuner. I2C is the OLED and the expander."""
    if hal.machine is None:
        return
    machine = hal.machine
    app.uart0 = machine.UART(
        0,
        baudrate=config.RS485_BAUD,
        tx=machine.Pin(config.RS485_TX),
        rx=machine.Pin(config.RS485_RX),
    )
    app.uart1 = machine.UART(
        1,
        baudrate=config.ATU_BAUD,
        tx=machine.Pin(config.ATU_TX),
        rx=machine.Pin(config.ATU_RX),
    )
    i2c = machine.I2C(0, scl=machine.Pin(config.I2C_SCL), sda=machine.Pin(config.I2C_SDA), freq=config.I2C_FREQ)
    app.oled = SSD1306(i2c, config.OLED_ADDR)
    app.oled.init()
    app.mcp = MCP23017(i2c, config.MCP23017_ADDR)
    app.mcp.write_iodir(0x9F, 0x80)
    app.mcp.write_pullups(0x1F, 0x00)
    app.mcp.enable_interrupts()
    _arm_uart(app.uart0, app.rs485, app.rs485_flags)
    _arm_uart(app.uart1, app.atu_ring, app.atu_flags)
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


def _interrupt(app: RemoteApp) -> None:
    """Read the expander once the pin interrupt has raised the flag."""
    if not app.mcp_flag.mcp:
        return
    if getattr(app, "mcp", None) is not None:
        app.mcp.read_gpio()
    app.mcp_flag.mcp = False


def run_production_pass(board: RemoteApp) -> None:
    """Read the clock once, then run the task list. Tests that set now_ms call run_once."""
    board.now_ms = hal.ticks_ms()
    run_once(board.tasks, interrupt=lambda: _interrupt(board), watchdog=hal.feed_watchdog)


if __name__ == "__main__":
    board = boot_devices("remote")
    while True:
        run_production_pass(board)
