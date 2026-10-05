# OLED text for both Picos. The pixels live in the SSD1306 driver.
# This module only builds the four tuner lines the operator reads.

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
