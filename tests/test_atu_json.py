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


def test_dispatched_status_is_retried_three_times_then_resource_offline():
    from common.hal import note_rx_byte
    from common.protocol import Frame, decode_frames, encode_frame
    from common.scheduler import run_once
    from remote.tasks import RemoteApp, build_remote_tasks

    app = RemoteApp()
    app.now_ms = 0
    for byte in encode_frame(Frame(1, 2, 7, Command.STA, b"")):
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.port_writes == [b'{"Status":true}\n']
    assert app.atu.busy is True
    app.now_ms = 500
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    app.now_ms = 1000
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.port_writes == [b'{"Status":true}\n'] * 3
    app.now_ms = 1500
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    assert app.atu.busy is False
    assert len(app.port_writes) == 3
    for byte in encode_frame(Frame(1, 2, 8, Command.HHH, b"")):
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    run_once(build_remote_tasks(app), interrupt=lambda: None, watchdog=lambda: None)
    err = decode_frames(bytes(app.tx))[0][-1]
    assert err.command is Command.ERR
    assert err.sequence == 8
    assert err.payload == bytes([3, 3, Command.STA.byte])
    sent = len(app.port_writes)
    for byte in encode_frame(Frame(1, 2, 9, Command.AM0, b"")):
        note_rx_byte(app.rs485, app.rs485_flags, byte)
    # AM0 after the tuner is idle should be allowed. The busy case is separate.
    busy = RemoteApp()
    busy.now_ms = 0
    for byte in encode_frame(Frame(1, 2, 1, Command.STA, b"")):
        note_rx_byte(busy.rs485, busy.rs485_flags, byte)
    run_once(build_remote_tasks(busy), interrupt=lambda: None, watchdog=lambda: None)
    for byte in encode_frame(Frame(1, 2, 2, Command.AM0, b"")):
        note_rx_byte(busy.rs485, busy.rs485_flags, byte)
    run_once(build_remote_tasks(busy), interrupt=lambda: None, watchdog=lambda: None)
    assert busy.port_writes == [b'{"Status":true}\n']
    refused = decode_frames(bytes(busy.tx))[0][-1]
    assert refused.payload[0] == ErrorCode.FAILED_TO_EXECUTE
    tune = RemoteApp()
    tune.now_ms = 0
    for byte in encode_frame(Frame(1, 2, 1, Command.TUN, b"")):
        note_rx_byte(tune.rs485, tune.rs485_flags, byte)
    run_once(build_remote_tasks(tune), interrupt=lambda: None, watchdog=lambda: None)
    tune.now_ms = 29999
    run_once(build_remote_tasks(tune), interrupt=lambda: None, watchdog=lambda: None)
    assert tune.atu.busy is True
    assert tune.port_writes == [b'{"Tune":true}\n']
    tune.now_ms = 30000
    run_once(build_remote_tasks(tune), interrupt=lambda: None, watchdog=lambda: None)
    assert tune.atu.busy is False
    assert tune.port_writes == [b'{"Tune":true}\n']
    assert sent == 3


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


def test_event_and_send_state_in_one_read_commits_forward():
    link = AtuLink()
    blob = b'{\n  "Event": "Tune"\n}\n' + _MULTILINE.replace(b'"Forward": 100.0', b'"Forward": 10.0').replace(
        b'"Power": 99.0', b'"Power": 9.0'
    )
    status = link.feed(blob)
    assert status.forward_w == 10.0
    assert status.antenna_w == 9.0
    assert link.last_status.forward_w == 10.0
    assert link._announced is False


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
