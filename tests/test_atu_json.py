from pathlib import Path

from common.commands import Command
from common.errors import ErrorCode
from remote.atu_link import AtuLink, encode_command

_MULTILINE = """\
{
  "Auto": true,
  "Bypass": false,
  "efficency": 99,
  "Power": 99.0,
  "Forward": 100.0,
  "SWR": 1.15,
  "Order": "LC",
  "Capacitance": 150,
  "Inductance": 1250
}
""".encode()


class _Port:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)


def test_second_send_while_waiting_fails():
    port = _Port()
    link = AtuLink(port)
    assert link.send(Command.STA, now_ms=0) is None
    assert port.writes == [b'{"Status":true}\n']
    assert link.busy is True
    assert link.send(Command.AM0, now_ms=10) is ErrorCode.FAILED_TO_EXECUTE
    assert port.writes == [b'{"Status":true}\n']


def test_status_is_retried_three_times():
    port = _Port()
    link = AtuLink(port)
    link.send(Command.STA, now_ms=0)
    link.poll(500)
    link.poll(1000)
    result = link.poll(1500)
    assert port.writes == [b'{"Status":true}\n', b'{"Status":true}\n', b'{"Status":true}\n']
    assert link.busy is False
    assert result is ErrorCode.RESOURCE_OFFLINE


def test_reply_on_first_try_sends_once():
    port = _Port()
    link = AtuLink(port)
    link.send(Command.STA, now_ms=0)
    link.feed(b'{"Forward":1.0}\n')
    link.poll(500)
    assert len(port.writes) == 1


def test_tune_uses_the_long_timeout():
    port = _Port()
    link = AtuLink(port)
    link.send(Command.TUN, now_ms=0)
    link.poll(29999)
    assert link.busy is True
    link.poll(30000)
    assert link.busy is False


def test_broken_json_is_data_corrupted():
    link = AtuLink(port=bytearray())
    assert link.feed(b'{"Forward":}\n') is ErrorCode.DATA_CORRUPTED
    status = link.feed(b'{"Forward":1.0}\n')
    assert status.forward_w == 1.0


def test_parse_multiline_send_state():
    status = AtuLink().feed(_MULTILINE)
    assert status.forward_w == 100.0
    assert status.antenna_w == 99.0
    assert status.efficiency_pct == 99
    assert status.swr == 1.15
    assert status.inductance_nh == 1250
    assert status.capacitance_pf == 150
    assert status.auto is True
    assert status.bypass is False
    assert status.order == "LC"


def test_event_object_is_ignored():
    link = AtuLink()
    assert link.feed(b'{\n  "Event": "Tune"\n}\n') is None


def test_partial_object_stays_buffered():
    link = AtuLink()
    assert link.feed(b'{\n  "Forward": 1.0') is None
    status = link.feed(b',\n  "Power": 1.0\n}\n')
    assert status.forward_w == 1.0
    assert status.antenna_w is None


def test_parse_status_with_source_spelling():
    link = AtuLink()
    plain = link.feed(b'{"Power":8.5,"SWR":1.23,"Inductance":110}\n')
    assert plain.forward_w == 8.5
    assert plain.antenna_w is None
    spelled = link.feed(b'{"Efficency":90,"Forward":4.0,"Power":3.5}\n')
    assert spelled.efficiency_pct == 90
    assert spelled.antenna_w == 3.5
    assert spelled.forward_w == 4.0


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
