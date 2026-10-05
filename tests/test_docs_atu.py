from pathlib import Path


def test_firmware_notes_pin_the_ukoda_hex():
    link = Path("docs/ATU_LINK.md").read_text(encoding="utf-8")
    notes = Path("atu100_firmware/README.md").read_text(encoding="utf-8")
    for text in (link, notes):
        assert "ATU-100_remote_PIC16F1938_20260412_1157.hex" in text
        assert "4800" in text
    assert "efficency" in link
    assert '{"x":true}' in link
    assert "RelayC" in link and "bit 7" in link
    assert "Forward" in link
    for phrase in ("MPLAB X", "XC8", "docker.sh", "pk2cmd", "// REMOTE LINK"):
        assert phrase in notes
    assert 'json_int("Forward", g_i_Power, sft)' in notes
    assert "send_state" in notes
    assert "do not compile" in notes.lower() or "does not compile" in notes.lower() or "not compile" in notes.lower()
