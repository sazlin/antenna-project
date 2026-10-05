from pathlib import Path


def test_bench_plan_starts_with_no_rf():
    text = Path("docs/TEST_PLAN.md").read_text(encoding="utf-8")
    no_rf = text.index("No RF")
    dummy = text.index("Dummy load")
    antennas = text.index("Antennas")
    assert no_rf < dummy < antennas
    no_rf_section = text[no_rf:dummy]
    dummy_section = text[dummy:antennas]
    antenna_section = text[antennas:]
    assert "all relays off" in no_rf_section.lower() or "relays off" in no_rf_section.lower()
    assert "wattmeter" in no_rf_section.lower()
    assert "low power" in dummy_section.lower()
    assert "dummy load" in dummy_section.lower()
    assert "one relay" in antenna_section.lower()
    assert "1 W" in antenna_section
