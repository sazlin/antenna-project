# CRC and RS485 frames between the master Pico and the remote Pico.
# The remote is the only board that drives antenna relays. This module
# never touches a relay coil. It only checks bytes on the U094 link.

import struct
from dataclasses import dataclass

from common.commands import CODE_TO_COMMAND, Command

START = 0x7E
END = 0x7F
ESCAPE = 0x7D
_SPECIAL = (START, END, ESCAPE)
_STATUS = struct.Struct("<BHHHHBBBB")
_FLAG_AUTO = 0x01
_FLAG_BYPASS = 0x02
_FLAG_ATU = 0x04
_FLAG_TEST = 0x08
_FLAG_EFFICIENCY = 0x10
_FLAG_POWER = 0x20
_FLAG_CL = 0x40


@dataclass(frozen=True)
class Status:
    """Tuner reading carried in a 13-byte SND payload."""

    auto: bool
    bypass: bool
    atu_link: bool
    test_mode: bool
    efficiency_valid: bool
    power_valid: bool
    order: str
    forward_w: float
    swr: float
    inductance_nh: int
    capacitance_pf: int
    efficiency_pct: int
    antenna: int
    error_code: int
    error_source: int


def _status_flags(status: Status) -> int:
    """Pack the mode bits. Bit 6 is CL order. LC leaves that bit clear."""
    flags = 0
    if status.auto:
        flags |= _FLAG_AUTO
    if status.bypass:
        flags |= _FLAG_BYPASS
    if status.atu_link:
        flags |= _FLAG_ATU
    if status.test_mode:
        flags |= _FLAG_TEST
    if status.efficiency_valid:
        flags |= _FLAG_EFFICIENCY
    if status.power_valid:
        flags |= _FLAG_POWER
    if status.order == "CL":
        flags |= _FLAG_CL
    return flags


def pack_status(status: Status) -> bytes:
    """Pack watts, SWR, L, and C into the fixed 13-byte status payload."""
    return _STATUS.pack(
        _status_flags(status),
        int(round(status.forward_w * 10)),
        int(round(status.swr * 100)),
        status.inductance_nh,
        status.capacitance_pf,
        status.efficiency_pct,
        status.antenna,
        status.error_code,
        status.error_source,
    )


def unpack_status(data: bytes) -> Status:
    """Restore a status payload. Raise ValueError when the buffer is short."""
    if len(data) != 13:
        raise ValueError(f"status payload is {len(data)} bytes, need 13")
    flags, forward, swr, inductance, capacitance, efficiency, antenna, error, source = _STATUS.unpack(data)
    return Status(
        auto=bool(flags & _FLAG_AUTO),
        bypass=bool(flags & _FLAG_BYPASS),
        atu_link=bool(flags & _FLAG_ATU),
        test_mode=bool(flags & _FLAG_TEST),
        efficiency_valid=bool(flags & _FLAG_EFFICIENCY),
        power_valid=bool(flags & _FLAG_POWER),
        order="CL" if flags & _FLAG_CL else "LC",
        forward_w=forward / 10,
        swr=swr / 100,
        inductance_nh=inductance,
        capacitance_pf=capacitance,
        efficiency_pct=efficiency,
        antenna=antenna,
        error_code=error,
        error_source=source,
    )


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
        if frame is None:
            # The opening start was a false sync. Look for the next 0x7E.
            index += 1
            continue
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
