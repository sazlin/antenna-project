from common.commands import Command
from common.errors import ErrorCode
from common.protocol import Action, Frame, RemoteLink, decode_frames, encode_frame


def _frame(command: Command, sequence: int, payload: bytes = b"") -> bytes:
    return encode_frame(Frame(1, 2, sequence, command, payload))


def test_boot_and_rst_send_ready():
    link = RemoteLink()
    reply, action = link.on_bytes(_frame(Command.HHH, 1))
    frames, _leftover = decode_frames(reply)
    assert action is None
    assert frames[0].command is Command.RST_RDY
    assert frames[0].command.mnemonic == "RST RDY"
    reply, _action = link.on_bytes(_frame(Command.HHH, 2))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ACK
    reply, action = link.on_bytes(_frame(Command.RST, 3))
    assert action == Action(Command.RST, None)
    ack, _leftover = decode_frames(link.finish(action))
    assert ack[0].command is Command.ACK
    assert ack[0].payload == bytes([Command.RST.byte])
    reply, _action = link.on_bytes(_frame(Command.HHH, 4))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.RST_RDY
    reply, _action = link.on_bytes(_frame(Command.HHH, 5))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ACK


def test_sta_replies_with_snd():
    link = RemoteLink()
    payload = bytes(range(13))
    link.notify_status(payload)
    reply, action = link.on_bytes(_frame(Command.STA, 9))
    assert action is None
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.SND
    assert frames[0].payload == payload
    assert frames[0].command is not Command.RS


def test_rpt_resends_previous_ack():
    link = RemoteLink()
    _reply, action = link.on_bytes(_frame(Command.AT3, 4))
    link.finish(action)
    reply, action = link.on_bytes(_frame(Command.RPT, 5))
    assert action is None
    frames, _leftover = decode_frames(reply)
    assert frames[0].sequence == 5
    assert frames[0].command is Command.ACK
    assert frames[0].payload == bytes([0x13])
    again, again_action = link.on_bytes(_frame(Command.RPT, 5))
    assert again == reply
    assert again_action is None


def test_rpt_without_cache_is_data_not_available():
    link = RemoteLink()
    reply, action = link.on_bytes(_frame(Command.RPT, 1))
    assert action is None
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ERR
    assert frames[0].payload[0] == ErrorCode.DATA_NOT_AVAILABLE
    assert frames[0].payload[1] == 2
    assert frames[0].payload[2] == 0x03


def test_sta_without_status_is_data_not_available():
    link = RemoteLink()
    reply, action = link.on_bytes(_frame(Command.STA, 8))
    assert action is None
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ERR
    assert list(frames[0].payload) == [2, 2, 0x04]


def test_status_handshake_survives_at2():
    link = RemoteLink()
    payload = bytes(range(13))
    link.notify_status(payload)
    reply, action = link.on_bytes(_frame(Command.HHH, 1))
    frames, _leftover = decode_frames(reply)
    assert action is None
    assert frames[0].command is Command.RS
    assert frames[0].payload == b""
    reply, action = link.on_bytes(_frame(Command.AT2, 2))
    assert action == Action(Command.AT2, antenna=2)
    ack, _leftover = decode_frames(link.finish(action))
    assert ack[0].command is Command.ACK
    assert ack[0].payload == bytes([0x12])
    reply, action = link.on_bytes(_frame(Command.HHH, 3))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.RS
    reply, _action = link.on_bytes(_frame(Command.RR, 4))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.SND
    assert frames[0].payload == payload
    reply, _action = link.on_bytes(_frame(Command.RR, 5))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ACK
    assert frames[0].payload == bytes([Command.RR.byte])
    reply, _action = link.on_bytes(_frame(Command.RCVD, 6))
    frames, _leftover = decode_frames(reply)
    assert frames[0].command is Command.ACK
    assert frames[0].payload == bytes([Command.RCVD.byte])


def test_duplicate_at1_does_not_repeat():
    link = RemoteLink()
    first_reply, action = link.on_bytes(_frame(Command.AT1, 7))
    assert first_reply is None
    assert action == Action(Command.AT1, antenna=1)
    again_reply, again_action = link.on_bytes(_frame(Command.AT1, 7))
    assert again_reply is None
    assert again_action is None
    ack = link.finish(action)
    third_reply, third_action = link.on_bytes(_frame(Command.AT1, 7))
    assert third_reply == ack
    assert third_action is None
    frames, leftover = decode_frames(ack)
    assert leftover == b""
    assert frames[0].command is Command.ACK
    assert frames[0].payload == bytes([0x11])
    assert frames[0].sequence == 7
