from pathlib import Path


def test_wiring_names_the_level_shift():
    text = Path("docs/WIRING.md").read_text(encoding="utf-8")
    for phrase in (
        "GPIO 8",
        "GPIO 9",
        "GPIO 0",
        "GPIO 1",
        "GPIO 4",
        "GPIO 5",
        "GPIO 10",
        "GPIO 11",
        "0x3C",
        "0x20",
        "GPIO 23",
        "GPIO 29",
        "74AHCT1G125",
        "2.2k",
        "3.3k",
        "RB1",
        "RB2",
        "RB0",
        "yellow",
        "white",
        "VBUS",
        "100k",
        "physical A/M and Bypass buttons are not usable",
        "do not wire fallback optocouplers and the UART at the same time",
    ):
        assert phrase in text
