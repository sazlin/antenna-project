# Pin numbers, timeouts, and button names for the master Pico.
# The remote uses the same header pins. GPIO 23, 24, 25, and 29 stay free
# because the Pico 2 W radio owns them. This board does not drive relays.

# I2C0 data. The OLED and the MCP23017 share this pin.
I2C_SDA = 8
# I2C0 clock.
I2C_SCL = 9
# I2C bus speed in hertz.
I2C_FREQ = 400_000
# RS485 TX from the Pico into the U094 yellow UART_RX wire.
RS485_TX = 0
# RS485 RX from the U094 white UART_TX wire.
RS485_RX = 1
# U094 link speed. 8N1. The module has no DE pin.
RS485_BAUD = 115200
# Reserved so the remote's tuner TX pin is not reused on this board.
ATU_TX = 4
# Reserved so the remote's tuner RX pin is not reused on this board.
ATU_RX = 5
# Tuner baud, unused on the master. Kept so the headers match.
ATU_BAUD = 4800
# MCP23017 INTA.
MCP_INTA = 10
# MCP23017 INTB.
MCP_INTB = 11
# SSD1306 I2C address.
OLED_ADDR = 0x3C
# MCP23017 I2C address.
MCP23017_ADDR = 0x20
# How often the master polls when it is idle, in milliseconds.
POLL_MS = 200
# How long the master waits for one reply.
REPLY_TIMEOUT_MS = 500
# Transmits of one command, counting the first.
REPLY_TRIES = 3
# Missed polls before Communication Lost.
MISS_LIMIT = 5
# Hardware watchdog period.
WATCHDOG_MS = 3000
# Forward sample older than this does not light RF Present.
POWER_STALE_MS = 1000
# RF Present lights only above this forward power.
HOT_SWITCH_WATTS = 1.0
# Decision 5 button names, in menu and panel order.
MASTER_BUTTONS = (
    "Up",
    "Down",
    "Left",
    "Right",
    "Select",
    "Tune",
    "A/M",
    "Bypass",
    "Antenna Select",
    "Menu",
)
# Active-low input bits on the MCP23017.
MASTER_BUTTON_BITS = {
    "Up": 0,
    "Down": 1,
    "Left": 2,
    "Right": 3,
    "Select": 4,
    "Tune": 5,
    "A/M": 6,
    "Bypass": 7,
    "Antenna Select": 8,
    "Menu": 9,
}
# Active-high LED bits. GPB2 is Link OK.
LED_LINK_OK = 1 << 2
# GPB3 Error.
LED_ERROR = 1 << 3
# GPB4 Auto Mode.
LED_AUTO = 1 << 4
# GPB5 Bypass.
LED_BYPASS = 1 << 5
# GPB6 RF Present.
LED_RF = 1 << 6
