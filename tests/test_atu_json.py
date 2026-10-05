from pathlib import Path

from common.commands import Command
from remote.atu_link import encode_command


def test_am0_is_auto_true_alone():
    encoded = encode_command(Command.AM0)
    assert encoded == b'{"Auto":true}\n'
    assert b"Bypass" not in encoded
    source = Path("remote/atu_link.py").read_text()
    sentence = (
        "AM0 turns Auto on and AM1 turns Auto off. "
        "BYP1 and TST1 turn those modes on. "
        "The Auto pair is reversed from the other pairs, matching the client spec."
    )
    assert sentence in source


def test_encode_am1_is_auto_false():
    assert encode_command(Command.AM1) == b'{"Auto":false}\n'


def test_encode_byp0_is_bypass_false():
    assert encode_command(Command.BYP0) == b'{"Bypass":false}\n'


def test_encode_byp1_is_bypass_true():
    assert encode_command(Command.BYP1) == b'{"Bypass":true}\n'


def test_encode_tune():
    assert encode_command(Command.TUN) == b'{"Tune":true}\n'


def test_encode_status():
    assert encode_command(Command.STA) == b'{"Status":true}\n'


def test_encode_reset():
    assert encode_command(Command.RST) == b'{"Reset":true}\n'
