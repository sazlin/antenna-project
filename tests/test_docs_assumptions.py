from pathlib import Path


def test_client_decisions_are_first():
    text = Path("docs/ASSUMPTIONS.md").read_text(encoding="utf-8")
    phrases = [
        "more than 1 W",
        "Keep the current antenna",
        "ukoda/ATU-100-remote",
        "TST0/TST1",
        "Antenna Select",
        "5 buttons",
        "100 ms",
        "GPIO 23, 24, 25 or 29",
    ]
    cursor = 0
    for phrase in phrases:
        found = text.find(phrase, cursor)
        assert found != -1
        cursor = found + len(phrase)
    for ident in [f"A{number}" for number in range(1, 22)]:
        assert ident in text
    assert "Forward" in text
    for name in ("REPLY_TIMEOUT_MS", "REMOTE_SILENCE_MS", "ATU_MODE", "common/hal.py"):
        assert name in text
    a12 = text.split("A12", 1)[1].split("A13", 1)[0]
    assert "Power" in a12
    assert "antenna watts" in a12
    assert "not forward watts times efficiency" in a12
    a21 = text.split("A21", 1)[1]
    assert "order" in a21
    assert "stored" in a21
