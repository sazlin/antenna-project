# Remote antenna switch

A master Pico polls a remote Pico over RS485. The remote drives one antenna relay and talks to the ATU-100 on a second UART.

```text
Radio  -- RF -->  ATU-100  -- serial 4800 -->  remote Pico  -- RS485 -->  master Pico
                      |                         relays
                      +-- OLED on each Pico
```

Quick start: wire the boards from [docs/WIRING.md](docs/WIRING.md), then flash them from [docs/FLASHING.md](docs/FLASHING.md). The host tests run with `python3 -m pytest tests -q` and do not need the hardware.
