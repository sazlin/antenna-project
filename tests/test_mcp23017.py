from common.mcp23017 import MCP23017, RelayLatch


class FakeI2C:
    def __init__(self) -> None:
        self.writes: list[tuple[int, int, int]] = []
        self.mem: dict[tuple[int, int], int] = {}

    def writeto_mem(self, addr: int, reg: int, buf: bytes) -> None:
        self.writes.append((addr, reg, buf[0]))
        self.mem[(addr, reg)] = buf[0]

    def readfrom_mem(self, addr: int, reg: int, nbytes: int) -> bytes:
        return bytes([self.mem.get((addr, reg), 0)])


def test_iodir_and_pullups():
    bus = FakeI2C()
    chip = MCP23017(bus, 0x20)
    chip.write_iodir(port_a=0xFF, port_b=0x1F)
    chip.write_pullups(port_a=0xFF, port_b=0x1F)
    assert bus.writes[:4] == [
        (0x20, 0x00, 0xFF),
        (0x20, 0x01, 0x1F),
        (0x20, 0x0C, 0xFF),
        (0x20, 0x0D, 0x1F),
    ]


def test_olat_write_uses_the_latch_registers():
    bus = FakeI2C()
    chip = MCP23017(bus, 0x20)
    chip.write_olat(0x00, 0x0F)
    assert (0x20, 0x14, 0x00) in bus.writes
    assert (0x20, 0x15, 0x0F) in bus.writes
    assert chip.read_olat() == (0x00, 0x0F)


def test_interrupts_are_open_drain():
    bus = FakeI2C()
    chip = MCP23017(bus, 0x20)
    chip.write_iodir(port_a=0xFF, port_b=0x1F)
    chip.enable_interrupts()
    assert (0x20, 0x04, 0xFF) in bus.writes
    assert (0x20, 0x05, 0x1F) in bus.writes
    assert (0x20, 0x0A, 0x04) in bus.writes


def test_relay_latch_keeps_the_opto_bits():
    bus = FakeI2C()
    chip = MCP23017(bus, 0x20)
    chip.write_olat(0x00, 0x70)
    latch = RelayLatch(chip)
    latch.write(0b0010)
    assert latch.read() == 0b0010
    assert chip.read_olat()[1] & 0x70 == 0x70
