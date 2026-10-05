# Serial link from the remote Pico to the ATU-100 on UART1.
# The master does not talk to the tuner. One JSON field goes out per line.
# AM0 turns Auto on and AM1 turns Auto off. BYP1 and TST1 turn those modes on. The Auto pair is reversed from the other pairs, matching the client spec.

import json
from dataclasses import dataclass

from common.commands import Command
from common.errors import ErrorCode

_OUTBOUND = {
    Command.AM0: b'{"Auto":true}\n',
    Command.AM1: b'{"Auto":false}\n',
    Command.BYP0: b'{"Bypass":false}\n',
    Command.BYP1: b'{"Bypass":true}\n',
    Command.TUN: b'{"Tune":true}\n',
    Command.STA: b'{"Status":true}\n',
    Command.RST: b'{"Reset":true}\n',
}


@dataclass
class TunerStatus:
    """One ukoda object after Forward and Power have been given their roles."""

    forward_w: float | None = None
    antenna_w: float | None = None
    efficiency_pct: int | None = None
    swr: float | None = None
    inductance_nh: int | None = None
    capacitance_pf: int | None = None
    auto: bool | None = None
    bypass: bool | None = None
    order: str | None = None


def _balanced_end(text: str) -> int | None:
    """Index just past the closing brace, or None while the object is still open."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    for index in range(start, len(text)):
        char = text[index]
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _number(value: object) -> float | None:
    """Return a JSON number as float. Missing fields stay None."""
    if value is None:
        return None
    return float(value)


def _status_from_object(obj: dict[str, object]) -> TunerStatus | None:
    """Apply the Forward and Power roles. An Event object is not a reading."""
    keys = set(obj)
    if "Event" in keys and keys <= {"Event"}:
        return None
    efficiency = obj.get("efficency", obj.get("Efficency"))
    forward = _number(obj.get("Forward"))
    power = _number(obj.get("Power"))
    if efficiency is None:
        antenna_w = None
        forward_w = forward if forward is not None else power
    else:
        antenna_w = power
        forward_w = forward
    inductance = obj.get("Inductance")
    capacitance = obj.get("Capacitance")
    return TunerStatus(
        forward_w=forward_w,
        antenna_w=antenna_w,
        efficiency_pct=None if efficiency is None else int(efficiency),
        swr=_number(obj.get("SWR")),
        inductance_nh=None if inductance is None else int(inductance),
        capacitance_pf=None if capacitance is None else int(capacitance),
        auto=obj.get("Auto"),
        bypass=obj.get("Bypass"),
        order=obj.get("Order"),
    )


class AtuLink:
    """Half-duplex ukoda port. feed parses whatever has arrived."""

    def __init__(self, port: object | None = None) -> None:
        """Hold the UART stand-in and an incomplete JSON buffer."""
        self.port = bytearray() if port is None else port
        self._rx = ""
        self.busy = False

    def feed(self, data: bytes) -> TunerStatus | ErrorCode | None:
        """Append bytes. A finished object that is not JSON is data corrupted."""
        self._rx += data.decode("utf-8")
        end = _balanced_end(self._rx)
        if end is None:
            return None
        piece = self._rx[:end]
        self._rx = self._rx[end:]
        try:
            obj = json.loads(piece)
        except json.JSONDecodeError:
            self.busy = False
            return ErrorCode.DATA_CORRUPTED
        self.busy = False
        return _status_from_object(obj)


def encode_command(command: Command) -> bytes:
    """Return the one-field ukoda line for a tuner command."""
    try:
        return _OUTBOUND[command]
    except KeyError as err:
        raise ValueError(f"no ukoda line for {command.mnemonic}") from err
