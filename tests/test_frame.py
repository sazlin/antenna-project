from common.commands import Command
from common.protocol import Frame, decode_frames, encode_frame


def test_encode_at1_matches_known_frame():
    frame = Frame(source=1, destination=2, sequence=1, command=Command.AT1, payload=b"")
    assert encode_frame(frame).hex() == "7e010201110047517f"


def test_payload_special_bytes_round_trip():
    payload = bytes([0x7E, 0x00, 0x7D, 0x7F])
    frame = Frame(source=1, destination=2, sequence=3, command=Command.SND, payload=payload)
    encoded = encode_frame(frame)
    assert b"\x7d\x5e" in encoded
    assert b"\x7d\x5d" in encoded
    assert b"\x7d\x5f" in encoded
    frames, leftover = decode_frames(encoded)
    assert leftover == b""
    assert len(frames) == 1
    assert frames[0].payload == payload


def test_decode_at1_known_frame():
    frames, leftover = decode_frames(bytes.fromhex("7e010201110047517f"))
    assert len(frames) == 1
    assert frames[0].command is Command.AT1
    assert frames[0].sequence == 1
    assert frames[0].payload == b""
    assert leftover == b""
