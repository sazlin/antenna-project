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


def screen_lines(reading: Reading) -> tuple[str, str, str, str]:
    """Build the four tuner lines. LC puts L above C. CL swaps them."""
    line1 = _line1(format_power(reading.forward_w), _marker(reading))
    inductance = format_inductance_nh(reading.inductance_nh)
    capacitance = format_capacitance_pf(reading.capacitance_pf)
    if reading.order == "CL":
        third, fourth = capacitance, inductance
    else:
        third, fourth = inductance, capacitance
    return line1, format_swr(reading.swr), third, fourth


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
