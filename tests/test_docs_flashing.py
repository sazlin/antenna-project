from pathlib import Path


def test_flashing_doc_names_the_firmware():
    text = Path("docs/FLASHING.md").read_text(encoding="utf-8")
    for phrase in (
        "v1.29.0",
        "RPI_PICO2_W",
        "mpremote",
        "cp -r common",
        "master/main.py",
        ":main.py",
        "BOOTSEL",
        "pk2cmd -PPIC16F1938 -GF",
    ):
        assert phrase in text
    lowered = text.lower()
    assert "back up" in lowered or "backup" in lowered
    assert "original" in lowered
