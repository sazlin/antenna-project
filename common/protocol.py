# CRC and RS485 frames between the master Pico and the remote Pico.
# The remote is the only board that drives antenna relays. This module
# never touches a relay coil. It only checks bytes on the U094 link.

from dataclasses import dataclass

from common.commands import CODE_TO_COMMAND, Command

START = 0x7E
END = 0x7F
ESCAPE = 0x7D
_SPECIAL = (START, END, ESCAPE)


@dataclass
class Frame:
    """One unescaped RS485 command after the start byte is stripped."""

    source: int
    destination: int
    sequence: int
    command: Command
    payload: bytes


def _body(frame: Frame) -> bytes:
    """Build source, destination, sequence, command, length, and payload."""
    return bytes(
        [
            frame.source,
            frame.destination,
            frame.sequence,
            frame.command.byte,
            len(frame.payload),
        ]
    ) + frame.payload


def _escape(data: bytes) -> bytes:
    """Hide start, end, and escape bytes so they cannot split the frame."""
    out = bytearray()
    for byte in data:
        if byte in _SPECIAL:
            out.append(ESCAPE)
            out.append(byte ^ 0x20)
        else:
            out.append(byte)
    return bytes(out)


def _unescape(data: bytes) -> bytes:
    """Restore a payload after the wire escape pairs are removed."""
    out = bytearray()
    index = 0
    while index < len(data):
        if data[index] == ESCAPE and index + 1 < len(data):
            out.append(data[index + 1] ^ 0x20)
            index += 2
        else:
            out.append(data[index])
            index += 1
    return bytes(out)


def encode_frame(frame: Frame) -> bytes:
    """Wrap a frame with the start byte, little-endian CRC, and end byte."""
    body = _body(frame)
    crc = crc16_ccitt(body)
    covered = body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    return bytes([START]) + _escape(covered) + bytes([END])


def _frame_from_body(body: bytes) -> Frame | None:
    """Turn an unescaped body into a frame when the length byte matches."""
    if len(body) < 5 or len(body) != 5 + body[4]:
        return None
    if body[3] not in CODE_TO_COMMAND:
        return None
    return Frame(
        source=body[0],
        destination=body[1],
        sequence=body[2],
        command=CODE_TO_COMMAND[body[3]],
        payload=body[5:],
    )


def _checked_frame(raw: bytes) -> Frame | None:
    """Accept raw body plus CRC only when both the CRC and the length match."""
    if len(raw) < 7:
        return None
    body, crc_lo, crc_hi = raw[:-2], raw[-2], raw[-1]
    if crc16_ccitt(body) != (crc_lo | (crc_hi << 8)):
        return None
    return _frame_from_body(body)


def _unescaped_end(data: bytes, start: int) -> int | None:
    """Find the end marker. An escaped 0x7F is payload, not the end of the frame."""
    index = start + 1
    size = len(data)
    while index < size:
        if data[index] == ESCAPE:
            index += 2
            continue
        if data[index] == END:
            return index
        index += 1
    return None


def decode_frames(data: bytes) -> tuple[list[Frame], bytes]:
    """Return every good frame. Bytes with no end marker stay in the leftover."""
    frames: list[Frame] = []
    index = 0
    size = len(data)
    while index < size:
        if data[index] != START:
            index += 1
            continue
        end = _unescaped_end(data, index)
        if end is None:
            return frames, data[index:]
        frame = _checked_frame(_unescape(data[index + 1 : end]))
        if frame is not None:
            frames.append(frame)
        index = end + 1
    return frames, b""


def crc16_ccitt(data: bytes) -> int:
    """Return CRC-16/CCITT-FALSE for data.

    Polynomial 0x1021, init 0xFFFF, no reflection, xorout 0.
    The on-wire form of this value is little-endian.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
