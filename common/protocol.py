# CRC and RS485 frames between the master Pico and the remote Pico.
# The remote is the only board that drives antenna relays. This module
# never touches a relay coil. It only checks bytes on the U094 link.

from dataclasses import dataclass

from common.commands import Command

START = 0x7E
END = 0x7F


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


def encode_frame(frame: Frame) -> bytes:
    """Wrap a frame with the start byte, little-endian CRC, and end byte."""
    body = _body(frame)
    crc = crc16_ccitt(body)
    return bytes([START]) + body + bytes([crc & 0xFF, (crc >> 8) & 0xFF, END])


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
