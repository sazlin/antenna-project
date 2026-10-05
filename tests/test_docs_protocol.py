from pathlib import Path

from common.commands import Command


def test_protocol_doc_has_the_at1_frame():
    text = Path("docs/PROTOCOL.md").read_text(encoding="utf-8")
    assert "7e010201110047517f" in text
    assert "CRC-16/CCITT-FALSE" in text
    for command in Command:
        assert command.mnemonic in text
    assert "The remote does not transmit until the master polls" in text
    assert "RS" in text and "RR" in text and "SND" in text and "RCVD" in text
