from common.commands import Command
from common.errors import ErrorCode
from common.protocol import Frame, RemoteLink, decode_frames, encode_frame


def test_hot_switch_err_payload():
    link = RemoteLink()
    link.on_bytes(encode_frame(Frame(1, 2, 4, Command.AT1, b"")))
    err = link.fail(Command.AT1, ErrorCode.HOT_SWITCH, source=2)
    frames, leftover = decode_frames(err)
    assert leftover == b""
    assert frames[0].command is Command.ERR
    assert frames[0].sequence == 4
    assert frames[0].payload == bytes([6, 2, 0x11])
    assert ErrorCode.COMMUNICATION_LOST.nature == "Communication Lost"
    natures = {code.nature for code in ErrorCode}
    for text in (
        "Failed to Execute Command",
        "Data Not Available",
        "Resource offline",
        "Communication Lost",
        "Data Corrupted",
    ):
        assert text in natures
