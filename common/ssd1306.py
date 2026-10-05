# SSD1306 128x64 on I2C 0x3C for both Picos.
# Four text rows sit on pages 0..3. The charge pump has to be on or the glass stays dark.
# There is no third-party display library.

_PAGE_WIDTH = 128
_PAGES = 8
_CHARS = "0123456789.%_ ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _glyph(char: str) -> bytes:
    """Build an 8 by 8 pattern that is not blank, so a missing table is obvious."""
    code = ord(char)
    rows = bytearray(8)
    for row in range(8):
        rows[row] = ((code + row * 17) * 13) & 0xFF or 0x01
    return bytes(rows)


_FONT = {char: _glyph(char) for char in _CHARS}


class SSD1306:
    """A small text panel. Commands use control byte 0x00."""

    def __init__(self, i2c: object, address: int = 0x3C) -> None:
        """Start with a dark framebuffer. init() turns the panel on."""
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(_PAGES * _PAGE_WIDTH)
        self.shown: tuple[str, ...] = ()

    def init(self) -> None:
        """Enable the charge pump, then turn the display off and back on."""
        for command in (0x8D, 0x14, 0xAE, 0xAF):
            self._command(command)

    def draw_char(self, page: int, column: int, char: str) -> None:
        """Draw one glyph. An unknown character is a programming error."""
        try:
            glyph = _FONT[char]
        except KeyError as err:
            raise ValueError(f"no glyph for {char!r}") from err
        start = page * _PAGE_WIDTH + column * 8
        self.buffer[start : start + 8] = glyph

    def show_lines(self, lines: tuple[str, ...]) -> None:
        """Draw up to four text rows onto pages 0..3."""
        self.shown = tuple(lines)
        self.buffer = bytearray(_PAGES * _PAGE_WIDTH)
        for row, text in enumerate(lines[:4]):
            for column, char in enumerate(text[:16]):
                self.draw_char(row, column, char)

    def _command(self, value: int) -> None:
        """Send one command. The first byte is the command control byte."""
        self.i2c.writeto(self.address, bytes([0x00, value]))
