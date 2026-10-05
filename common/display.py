# OLED text for both Picos. The pixels live in the SSD1306 driver.
# This module only builds the four tuner lines the operator reads.

def format_power(watts: float) -> str:
    """Format watts with one decimal, the way the ATU-100 power line does."""
    return f"{watts:.1f}W"


def format_swr(swr: float) -> str:
    """Format SWR with two decimals and no unit."""
    return f"{swr:.2f}"
