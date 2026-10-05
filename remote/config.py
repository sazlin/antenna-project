# Pin numbers, timeouts, and button names for the remote Pico.
# The header matches the master. Relays, the tuner UART, and the optocouplers
# are only wired on this board. GPIO 23, 24, 25, and 29 stay free.

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
# UART1 TX to the ATU-100 RB2, through the 74AHCT1G125.
ATU_TX = 4
# UART1 RX from the ATU-100 RB1, through the resistor divider.
ATU_RX = 5
# Ukoda firmware baud.
ATU_BAUD = 4800
# MCP23017 INTA.
MCP_INTA = 10
# MCP23017 INTB.
MCP_INTB = 11
# SSD1306 I2C address.
OLED_ADDR = 0x3C
# MCP23017 I2C address.
MCP23017_ADDR = 0x20
# serial uses the tuner UART. fallback uses the optocouplers instead.
ATU_MODE = "serial"
# Break-before-make delay. Flyback diodes can hold a coil for about this long.
RELAY_DELAY_MS = 100
# Refuse an antenna change above this forward power.
HOT_SWITCH_WATTS = 1.0
# Set false to allow a change while transmitting.
HOT_SWITCH_ENABLED = True
# A forward sample older than this does not block a change.
POWER_STALE_MS = 1000
# How often an idle master polls. The remote uses it only as documentation of the link.
POLL_MS = 200
# Master reply window. Documented here so one file lists the link timers.
REPLY_TIMEOUT_MS = 500
# Master transmit count for one command.
REPLY_TRIES = 3
# Master misses before Communication Lost.
MISS_LIMIT = 5
# Ukoda reply window for a normal command.
ATU_TIMEOUT_MS = 500
# Ukoda writes, counting the first.
ATU_TRIES = 3
# How long a tune may stay busy.
TUNE_TIMEOUT_MS = 30000
# Silence after the last accepted master frame before this board shows Communication Lost.
REMOTE_SILENCE_MS = 2000
# Seven inductors, so the relay mask runs 0..127.
INDUCTOR_COUNT = 7
# Seven capacitors, same mask width.
CAPACITOR_COUNT = 7
# Hardware watchdog period.
WATCHDOG_MS = 3000
# Decision 6. Five buttons, no Tune key on this board.
REMOTE_BUTTONS = ("Up", "Down", "Left", "Right", "Select")
# GPA0 through GPA4, active low.
REMOTE_BUTTON_BITS = {"Up": 0, "Down": 1, "Left": 2, "Right": 3, "Select": 4}
# GPA5 Link OK, active high.
LED_LINK_OK = 1 << 5
# GPA6 Error, active high.
LED_ERROR = 1 << 6
