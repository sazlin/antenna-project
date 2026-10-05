# OLED text for both Picos. The pixels live in the SSD1306 driver.
# This module only builds the four tuner lines the operator reads.

from dataclasses import dataclass


@dataclass
class Reading:
    """The tuner numbers that become the four OLED lines."""

    forward_w: float
    swr: float
    inductance_nh: int
    capacitance_pf: int
    auto: bool
    bypass: bool
    order: str
    efficiency: int | None = None
    antenna_w: float | None = None


def _marker(reading: Reading) -> str:
    """Bypass wins over Auto because the stock firmware draws the underscore last."""
    if reading.bypass:
        return "_"
    if reading.auto:
        return "."
    return " "


def _line1(text: str, marker: str) -> str:
    """Pad a power reading so the mode marker sits in column 16."""
    return f"{text:<15}{marker}"


def _efficiency_screen(reading: Reading) -> bool:
    """The loss screen starts at 1.0 W, and only when both power numbers exist."""
    if reading.forward_w < 1.0:
        return False
    if reading.efficiency is None or reading.antenna_w is None:
        return False
    return True


def render_banner(text: str) -> tuple[str, str, str, str]:
    """Wrap a fault on spaces into four lines of at most 16 characters."""
    lines = ["", "", "", ""]
    row = 0
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= 16:
            current = candidate
            continue
        lines[row] = current
        row += 1
        current = word
    if current:
        lines[row] = current
    return (lines[0], lines[1], lines[2], lines[3])


def _reading_from_state(state: object) -> Reading:
    """Copy the tuner fields publish needs. The banner is handled separately."""
    return Reading(
        forward_w=state.forward_w or 0.0,
        swr=state.swr or 0.0,
        inductance_nh=state.inductance_nh or 0,
        capacitance_pf=state.capacitance_pf or 0,
        auto=state.auto,
        bypass=state.bypass,
        order=state.order or "LC",
        efficiency=state.efficiency_pct,
        antenna_w=state.antenna_w,
    )


def publish(state: object, panel: object) -> None:
    """Send the banner when one is set, otherwise the tuner screen."""
    if state.banner:
        lines = render_banner(state.banner)
    else:
        lines = screen_lines(_reading_from_state(state))
    panel.show_lines(lines)


def screen_lines(reading: Reading) -> tuple[str, str, str, str]:
    """Build the four tuner lines. LC puts L above C. CL swaps them."""
    line1 = _line1(format_power(reading.forward_w), _marker(reading))
    swr = format_swr(reading.swr)
    if _efficiency_screen(reading):
        percent = min(reading.efficiency, 99)
        return line1, swr, format_power(reading.antenna_w), f"{percent}%"
    inductance = format_inductance_nh(reading.inductance_nh)
    capacitance = format_capacitance_pf(reading.capacitance_pf)
    if reading.order == "CL":
        third, fourth = capacitance, inductance
    else:
        third, fourth = inductance, capacitance
    return line1, swr, third, fourth


def format_power(watts: float) -> str:
    """Format watts with one decimal, the way the ATU-100 power line does."""
    return f"{watts:.1f}W"


def format_inductance_nh(nanohenries: int) -> str:
    """Convert tuner nanohenries to the microhenry text on the L line."""
    return f"{nanohenries / 1000:.2f}uH"


def format_capacitance_pf(picofarads: int) -> str:
    """Format capacitance as an integer picofarad count."""
    return f"{int(picofarads)}pF"


def format_swr(swr: float) -> str:
    """Format SWR with two decimals and no unit."""
    return f"{swr:.2f}"


class DisplayBuffer:
    """Four text lines, an 8-line scrollback, and the highlighted menu row."""

    def __init__(self) -> None:
        """Start blank. Nothing is highlighted until the menu opens."""
        self._lines = ["", "", "", ""]
        self._scroll: list[str] = []
        self._highlight: int | None = None

    def write_line(self, number: int, text: str) -> None:
        """Replace one of the four visible lines. Lines are numbered 1 to 4."""
        self._lines[self._index(number)] = text

    def line(self, number: int) -> str:
        """Return one visible line."""
        return self._lines[self._index(number)]

    def write_char(self, number: int, column: int, char: str) -> None:
        """Put one character in a 1-based column of a visible line."""
        index = self._index(number)
        current = self._lines[index].ljust(column)
        self._lines[index] = current[: column - 1] + char + current[column:]

    def push_scroll(self, text: str) -> None:
        """Keep the newest eight scrollback lines and drop the oldest."""
        self._scroll.append(text)
        if len(self._scroll) > 8:
            self._scroll.pop(0)

    def scroll_lines(self) -> list[str]:
        """Return the stored scrollback, oldest first."""
        return list(self._scroll)

    def highlight(self) -> int | None:
        """Return the highlighted row, or None when the menu is closed."""
        return self._highlight

    def set_highlight(self, number: int) -> None:
        """Mark a visible row. Zero is not a row."""
        self._highlight = self._index(number) + 1

    def _index(self, number: int) -> int:
        """Convert a 1-based line number to a list index."""
        if number not in (1, 2, 3, 4):
            raise ValueError(f"line {number} is not 1..4")
        return number - 1
