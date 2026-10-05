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

    def __init__(
        self,
        port: object | None = None,
        *,
        timeout_ms: int = 500,
        tries: int = 3,
        tune_timeout_ms: int = 30000,
    ) -> None:
        """Hold the UART stand-in. One command is outstanding at a time."""
        self.port = bytearray() if port is None else port
        self.timeout_ms = timeout_ms
        self.tries = tries
        self.tune_timeout_ms = tune_timeout_ms
        self._rx = ""
        self.busy = False
        self._command: Command | None = None
        self._sent_ms = 0
        self._attempt = 0
        self.last_status: TunerStatus | None = None
        self._announced = False

    def begin(self, line: bytes, command: Command, now_ms: int) -> ErrorCode | None:
        """Send one already-encoded line and wait for its reply."""
        if self.busy:
            return ErrorCode.FAILED_TO_EXECUTE
        self._line = line
        self._command = command
        self._attempt = 0
        self.port.write(line)
        self.busy = True
        self._sent_ms = now_ms
        self._attempt = 1
        return None

    def send(self, command: Command, now_ms: int) -> ErrorCode | None:
        """Write one line unless a reply is already outstanding."""
        return self.begin(encode_command(command), command, now_ms)

    def poll(self, now_ms: int) -> ErrorCode | None:
        """Retry a normal command three times. Tune waits out the long timer."""
        if not self.busy or self._command is None:
            return None
        limit = self.tune_timeout_ms if self._command is Command.TUN else self.timeout_ms
        if now_ms - self._sent_ms < limit:
            return None
        if self._command is not Command.TUN and self._attempt < self.tries:
            self._write(self._command, now_ms)
            return None
        self.busy = False
        self._attempt = 0
        return ErrorCode.RESOURCE_OFFLINE

    def _write(self, command: Command, now_ms: int) -> None:
        """Repeat the outstanding line. Tune is not repeated."""
        self.port.write(self._line)
        self.busy = True
        self._command = command
        self._sent_ms = now_ms
        self._attempt += 1

    def feed(self, data: bytes) -> TunerStatus | ErrorCode | None:
        """Append bytes and take every complete object. A partial tail stays buffered."""
        self._rx += data.decode("utf-8")
        found: TunerStatus | None = None
        broken = False
        while True:
            end = _balanced_end(self._rx)
            if end is None:
                break
            piece = self._rx[:end]
            self._rx = self._rx[end:]
            try:
                obj = json.loads(piece)
            except json.JSONDecodeError:
                self.busy = False
                self._attempt = 0
                broken = True
                continue
            self.busy = False
            self._attempt = 0
            status = _status_from_object(obj)
            if status is None:
                continue
            self.last_status = status
            self._announced = False
            found = status
        if found is not None:
            return found
        if broken:
            return ErrorCode.DATA_CORRUPTED
        return None


class TestMode:
    """Direct L and C steps. Bit 7 is the CL/LC order bit and it is only on RelayC."""

    def __init__(self, inductor_count: int = 7, capacitor_count: int = 7) -> None:
        """Start out of test mode. Seven elements can count from 0 through 127."""
        self.active = False
        self.step = 0
        self._bank = "L"
        self._l_ceiling = (1 << inductor_count) - 1
        self._c_ceiling = (1 << capacitor_count) - 1

    def command(self, command: Command) -> bytes | None:
        """Return one relay line, or None for TST1 which only enters the mode."""
        if command is Command.TST1:
            self.active = True
            self.step = 0
            return None
        if command is Command.TST0:
            self.active = False
            return b'{"Reset":true}\n'
        if command is Command.TSC:
            self._bank = "C"
            return self._line()
        if command is Command.TSL:
            self._bank = "L"
            return self._line()
        if command is Command.TUP:
            ceiling = self._c_ceiling if self._bank == "C" else self._l_ceiling
            self.step = min(ceiling, self.step + 1)
            return self._line()
        if command is Command.TDN:
            self.step = max(0, self.step - 1)
            return self._line()
        return None

    def _line(self) -> bytes:
        """RelayI is the L step. RelayC is the C step with bit 7 set for LC order."""
        if self._bank == "C":
            return f'{{"RelayC":{self.step | 0x80}}}\n'.encode()
        return f'{{"RelayI":{self.step}}}\n'.encode()


def encode_command(command: Command) -> bytes:
    """Return the one-field ukoda line for a tuner command."""
    try:
        return _OUTBOUND[command]
    except KeyError as err:
        raise ValueError(f"no ukoda line for {command.mnemonic}") from err
