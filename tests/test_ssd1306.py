from common.display import publish
from common.ssd1306 import SSD1306
from common.state import LinkState


class FakeI2C:
    def __init__(self) -> None:
        self.writes: list[tuple[int, bytes]] = []

    def writeto(self, addr: int, buf: bytes) -> None:
        self.writes.append((addr, bytes(buf)))


def test_init_turns_the_panel_on():
    bus = FakeI2C()
    panel = SSD1306(bus, 0x3C)
    panel.init()
    commands = [buf[1] for addr, buf in bus.writes if addr == 0x3C and buf[0] == 0x00]
    assert 0x8D in commands
    assert 0x14 in commands
    assert 0xAE in commands
    assert 0xAF in commands
    charge = commands.index(0x8D)
    assert commands[charge + 1] == 0x14


def test_letter_a_is_not_blank():
    panel = SSD1306(FakeI2C(), 0x3C)
    panel.draw_char(0, 0, "A")
    block = bytes(panel.buffer[0:8])
    assert block != bytes(8)
    assert any(block)


def test_publish_sends_screen_lines():
    panel = SSD1306(FakeI2C(), 0x3C)
    state = LinkState(
        forward_w=5.0,
        swr=1.15,
        inductance_nh=1250,
        capacitance_pf=150,
        auto=False,
        bypass=False,
        order="LC",
        efficiency_pct=None,
        antenna_w=None,
        banner="",
    )
    publish(state, panel)
    assert panel.shown[0].endswith(" ")
    assert panel.shown[1] == "1.15"
    assert panel.shown[2] == "1.25uH"
    assert panel.shown[3] == "150pF"
    assert any(panel.buffer[128:136])
