# MCP23017 on I2C address 0x20 for both Picos.
# Buttons are inputs with pull-ups. Relay coils and LEDs are outputs.
# The remote relay bank is the low four bits of port B. Optocoupler bits stay put.

_IODIRA = 0x00
_IODIRB = 0x01
_GPINTENA = 0x04
_GPINTENB = 0x05
_IOCON = 0x0A
_GPPUA = 0x0C
_GPPUB = 0x0D
_OLATA = 0x14
_OLATB = 0x15
_OPEN_DRAIN = 0x04
_RELAY_MASK = 0x0F


class MCP23017:
    """Register writes for one expander. The bus is injected so the host can fake it."""

    def __init__(self, i2c: object, address: int = 0x20) -> None:
        """Remember the bus and the last direction bytes for the interrupt enable."""
        self.i2c = i2c
        self.address = address
        self._iodir = (0, 0)

    def write_iodir(self, port_a: int, port_b: int) -> None:
        """Set pin direction. A 1 bit is an input."""
        self._iodir = (port_a, port_b)
        self._write(_IODIRA, port_a)
        self._write(_IODIRB, port_b)

    def write_pullups(self, port_a: int, port_b: int) -> None:
        """Enable pull-ups on the button pins."""
        self._write(_GPPUA, port_a)
        self._write(_GPPUB, port_b)

    def write_olat(self, port_a: int, port_b: int) -> None:
        """Write the output latch. Read this back to confirm a relay coil."""
        self._write(_OLATA, port_a)
        self._write(_OLATB, port_b)

    def read_olat(self) -> tuple[int, int]:
        """Return the latched output bytes for port A and port B."""
        return self._read(_OLATA), self._read(_OLATB)

    def enable_interrupts(self) -> None:
        """Interrupt on the input pins. INT is open drain so both pins can share a wire."""
        self._write(_GPINTENA, self._iodir[0])
        self._write(_GPINTENB, self._iodir[1])
        self._write(_IOCON, _OPEN_DRAIN)

    def _write(self, reg: int, value: int) -> None:
        """One register write."""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def _read(self, reg: int) -> int:
        """One register read."""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]


class RelayLatch:
    """The four antenna coils. set_antenna reads and writes this object."""

    def __init__(self, chip: MCP23017) -> None:
        """Use port B bits 0..3. Leave the optocoupler bits alone."""
        self.chip = chip

    def read(self) -> int:
        """Return the coil bits only."""
        _port_a, port_b = self.chip.read_olat()
        return port_b & _RELAY_MASK

    def write(self, mask: int) -> None:
        """Replace the coil bits and keep GPB4..GPB6 as they were."""
        port_a, port_b = self.chip.read_olat()
        merged = (port_b & ~_RELAY_MASK) | (mask & _RELAY_MASK)
        self.chip.write_olat(port_a, merged)
