# Master Pico entry. Flash this file to /main.py along with the common and master packages.
# The master has no relay coils. Boot only starts the watchdog.
# The repeating task list is started from boot_devices.

from common import hal
from common.mcp23017 import MCP23017
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


def _interrupt(app: MasterApp) -> None:
    """The expander interrupt only sets a flag."""
    del app


if __name__ == "__main__":
    board = boot_devices("master")
    while True:
        run_once(board.tasks, interrupt=lambda: _interrupt(board), watchdog=lambda: None)
