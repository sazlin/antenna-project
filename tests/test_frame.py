from common.commands import Command
from common.protocol import Frame, decode_frames, encode_frame


def test_encode_at1_matches_known_frame():
    frame = Frame(source=1, destination=2, sequence=1, command=Command.AT1, payload=b"")
    assert encode_frame(frame).hex() == "7e010201110047517f"


def test_length_mismatch_is_dropped():
    from common.protocol import crc16_ccitt

    different = bytes([0x01, 0x02, 0x01, 0x11, 0x01, 0xAA])
    crc = crc16_ccitt(different)
    claimed = bytes([0x01, 0x02, 0x01, 0x11, 0x02, 0xAA, crc & 0xFF, (crc >> 8) & 0xFF])
    bad = bytes([0x7E]) + claimed + bytes([0x7F])
    valid = bytes.fromhex("7e010201110047517f")
    present = bytes([0x01, 0x02, 0x01, 0x11, 0x02, 0xAA])
    present_crc = crc16_ccitt(present)
    length_only = bytes([0x7E]) + present + bytes([present_crc & 0xFF, (present_crc >> 8) & 0xFF, 0x7F])
    frames, _leftover = decode_frames(bad + length_only + valid)
    assert [frame.command for frame in frames] == [Command.AT1]
    assert all(frame.payload != bytes([0xAA]) for frame in frames)


def test_bad_crc_is_dropped():
    bad = bytes.fromhex("7e010201110000517f")
    frames, leftover = decode_frames(bad)
    assert frames == []
    assert bad not in leftover
    stream = bad + bytes([0x7E]) + bytes.fromhex("7e010201110047517f")
    frames, leftover = decode_frames(stream)
    assert [frame.command for frame in frames] == [Command.AT1]
    assert leftover == b""


def test_truncated_frame_waits():
    partial = bytes.fromhex("7e010201110047")
    frames, leftover = decode_frames(partial)
    assert frames == []
    assert leftover == partial


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
