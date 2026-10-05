# Wiring

Both Pico 2 W boards use the same header. The expander bit maps are not the same, because the master has more buttons and the remote has the relay coils.

## Pico pins that must stay open

GPIO 23 is wireless power-on. GPIO 24 is wireless SPI data. GPIO 25 is wireless SPI chip select. GPIO 29 is wireless SPI clock and VSYS sense. Do not connect them.

## Shared header

| Signal | GPIO | Notes |
| --- | --- | --- |
| RS485 TX to U094 | GPIO 0 | Yellow wire, unit UART_RX |
| RS485 RX from U094 | GPIO 1 | White wire, unit UART_TX |
| ATU TX | GPIO 4 | Reserved on the master |
| ATU RX | GPIO 5 | Reserved on the master |
| I2C0 SDA | GPIO 8 | OLED and MCP23017 |
| I2C0 SCL | GPIO 9 | 400 kHz |
| MCP23017 INTA | GPIO 10 | 10k to 3.3 V |
| MCP23017 INTB | GPIO 11 | 10k to 3.3 V |

OLED address `0x3C`. MCP23017 address `0x20`.

## U094 RS485

HY2.0-4P: black GND, red 5 V from Pico VBUS, yellow unit UART_RX to Pico GPIO 0, white unit UART_TX to Pico GPIO 1. Schematic `SCH_UNIT_ISO485` v1.1 level-shifts the Grove data pins for a 3.3 V host. There is no DE pin. Fit the supplied 120 ohm resistor across A and B at the remote unit only.

## ATU-100 levels

The PIC16F1938 on the EXT board runs at 5 V. RB1 is ukoda TXD (`LATB1`). RB2 is ukoda RXD (`PORTBbits.RB2`). PORTB inputs are Schmitt triggers, so a valid high is 0.8 times 5 V, which is 4.0 V. Pico 3.3 V is not a valid high into RB2, and 5 V out of RB1 exceeds the Pico absolute maximum.

Up path: Pico GPIO 4 into a 74AHCT1G125 powered from the tuner 5 V rail. Output through 1k to RB2. 74AHCT treats 3.3 V as a high.

Down path: 2.2k from RB1 to Pico GPIO 5, 3.3k from GPIO 5 to ground. That is 3.0 V at the Pico.

Common ground between the Pico and the tuner logic ground.

The physical A/M and Bypass buttons are not usable with the ukoda serial firmware. Do not wire fallback optocouplers and the UART at the same time. Both want RB1 and RB2. In short, do not wire fallback optocouplers and the UART at the same time.

## Relays and fallback optos

Relay opto inputs have a 100k pull-down so a floating expander cannot energize a coil during boot.

Fallback optos, only when `ATU_MODE` is `fallback`: GPB4 across Tune (RB0 to ground), GPB5 across A/M (RB1 to ground), GPB6 across Bypass (RB2 to ground), 330 ohm into each opto LED, active high. Serial mode uses the UART parts instead and leaves those opto drivers unpopulated.

## Expander and OLED

MCP23017 RESET held high with 10k to 3.3 V. INTA and INTB each have 10k to 3.3 V. I2C pull-ups: use the ones on the Adafruit board and the OLED. Do not add a second pair.

Master inputs, active low with pull-ups: GPA0 Up, GPA1 Down, GPA2 Left, GPA3 Right, GPA4 Select, GPA5 Tune, GPA6 A/M, GPA7 Bypass, GPB0 Antenna Select, GPB1 Menu. LED outputs, active high: GPB2 Link OK, GPB3 Error, GPB4 Auto Mode, GPB5 Bypass, GPB6 RF Present.

Remote inputs: GPA0 Up through GPA4 Select. LED outputs: GPA5 Link OK, GPA6 Error. GPB0 through GPB3 are relays 1 through 4. GPB4 Tune opto, GPB5 A/M opto, GPB6 Bypass opto, used only in fallback mode.
