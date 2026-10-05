# Remote Pico entry. Flash this file to /main.py along with the common and remote packages.
# Boot opens every relay before the watchdog starts, so a stuck coil cannot sit
# through a reset. The repeating task list is started from boot_devices.

from common import hal
from common.mcp23017 import MCP23017
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
    boot_remote(app.latch, events)
    app.boot_events = events
    _open_buses(app)
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


def _interrupt(app: RemoteApp) -> None:
    """The expander interrupt only sets a flag. The pass reads the chip later."""
    if app.mcp_flag.mcp:
        app.mcp_flag.mcp = False


def run_production_pass(board: RemoteApp) -> None:
    """Read the clock once, then run the task list. Tests that set now_ms call run_once."""
    board.now_ms = hal.ticks_ms()
    run_once(board.tasks, interrupt=lambda: _interrupt(board), watchdog=lambda: None)


if __name__ == "__main__":
    board = boot_devices("remote")
    while True:
        run_production_pass(board)
