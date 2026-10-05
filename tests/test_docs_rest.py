from pathlib import Path


def test_root_readme_points_at_the_project_readme():
    root = Path("README.md").read_text(encoding="utf-8")
    assert "docs/README.md" in root
    assert root.strip() != "antenna-project"
    assert root.strip() != "# antenna-project"


def test_customizing_names_the_files():
    text = Path("docs/CUSTOMIZING.md").read_text(encoding="utf-8")
    assert "common/commands.py" in text
    assert "master/config.py" in text
    assert "common/menu.py" in text
    assert "RELAY_DELAY_MS" in text


def test_project_readme_points_at_wiring_and_flashing():
    text = Path("docs/README.md").read_text(encoding="utf-8")
    for word in ("master", "remote", "RS485", "ATU-100"):
        assert word in text
    assert "docs/WIRING.md" in text
    assert "docs/FLASHING.md" in text


def test_summary_is_honest_about_the_host_run():
    text = Path("SUMMARY.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "host test" in lowered
    assert "without hardware" in lowered or "no hardware" in lowered
    assert "ATU-100_remote_PIC16F1938_20260412_1157.hex" in text
    assert "not flashed" in lowered
    assert "Forward" in text
    assert "not compiled" in lowered
    for phrase in (
        "more than 1 W",
        "Keep the current antenna",
        "ukoda",
        "TST0/TST1",
        "Antenna Select",
        "5 buttons",
        "100 ms",
        "GPIO 23",
    ):
        assert phrase in text
