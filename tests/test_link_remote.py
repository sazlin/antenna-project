from common.commands import Command
from common.protocol import Action, Frame, RemoteLink, decode_frames, encode_frame


def _frame(command: Command, sequence: int, payload: bytes = b"") -> bytes:
    return encode_frame(Frame(1, 2, sequence, command, payload))


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
