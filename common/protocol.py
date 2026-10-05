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
    return Frame(
        source=body[0],
        destination=body[1],
        sequence=body[2],
        command=CODE_TO_COMMAND[body[3]],
        payload=body[5:],
    )


def decode_frames(data: bytes) -> tuple[list[Frame], bytes]:
    """Decode one complete unescaped frame. Anything else is not delivered."""
    if len(data) < 9 or data[0] != START or data[-1] != END:
        return [], b""
    raw = _unescape(data[1:-1])
    body, crc_lo, crc_hi = raw[:-2], raw[-2], raw[-1]
    if crc16_ccitt(body) != (crc_lo | (crc_hi << 8)):
        return [], b""
    frame = _frame_from_body(body)
    if frame is None:
        return [], b""
    return [frame], b""


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
