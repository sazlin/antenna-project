# CRC and RS485 frames between the master Pico and the remote Pico.
# The remote is the only board that drives antenna relays. This module
# never touches a relay coil. It only checks bytes on the U094 link.

from __future__ import annotations

import struct
from dataclasses import dataclass

from common.commands import CODE_TO_COMMAND, Command
from common.errors import ErrorCode

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


@dataclass
class _Pending:
    """One master command still waiting for the remote's reply."""

    sequence: int
    command: Command
    payload: bytes
    tries: int
    sent_ms: int
    raw: bytes


class MasterLink:
    """Master side of the polled RS485 link. Time is passed in. It does not sleep."""

    def __init__(
        self,
        *,
        poll_ms: int,
        reply_timeout_ms: int,
        reply_tries: int,
        miss_limit: int,
    ) -> None:
        """Remember the poll, retry, and link-loss limits from config."""
        self.poll_ms = poll_ms
        self.reply_timeout_ms = reply_timeout_ms
        self.reply_tries = reply_tries
        self.miss_limit = miss_limit
        self.misses = 0
        self.link_lost = False
        self.log: list[str] = []
        self._sequence = 1
        self._pending: _Pending | None = None
        self._next_poll_ms = poll_ms
        self._phase = "idle"
        self._status: Status | None = None
        self._buffer = bytearray()
        self._queue: list[tuple[Command, bytes]] = []

    def enqueue(self, command: Command, payload: bytes = b"") -> None:
        """Queue a command to send on the next idle poll instead of HHH."""
        self._queue.append((command, payload))

    def poll(self, now_ms: int) -> bytes | None:
        """Send the next master frame, or None while a reply is still in time."""
        if self._pending is not None:
            return self._wait_or_retry(now_ms)
        if self._phase == "saw_rs":
            return self._transmit(Command.RR, b"", now_ms)
        if self._phase == "saw_snd":
            raw = self._transmit(Command.RCVD, b"", now_ms)
            self._phase = "idle"
            return raw
        if now_ms < self._next_poll_ms:
            return None
        if self._queue:
            command, payload = self._queue.pop(0)
            return self._transmit(command, payload, now_ms)
        return self._transmit(Command.HHH, b"", now_ms)

    def feed(self, data: bytes) -> None:
        """Accept remote bytes. An ACK for the open sequence frees the next poll."""
        self._buffer.extend(data)
        frames, leftover = decode_frames(bytes(self._buffer))
        self._buffer = bytearray(leftover)
        for frame in frames:
            self._accept(frame)

    def status(self) -> Status | None:
        """Return the last SND payload the remote delivered, if one has arrived."""
        return self._status

    def display_banner(self) -> str:
        """Return the link-loss line, or an empty string while the remote answers."""
        if self.link_lost:
            return "Communication Lost"
        return ""

    def _transmit(self, command: Command, payload: bytes, now_ms: int) -> bytes:
        """Send a new sequence. Sequence 0 is skipped so a cleared counter cannot alias."""
        sequence = self._sequence
        self._sequence = 1 if sequence == 255 else sequence + 1
        frame = Frame(1, 2, sequence, command, payload)
        raw = encode_frame(frame)
        self._pending = _Pending(sequence, command, payload, 1, now_ms, raw)
        self.log.append(f"TX {command.mnemonic}")
        return raw

    def _wait_or_retry(self, now_ms: int) -> bytes | None:
        """Repeat the same frame until reply_tries, then count one miss."""
        pending = self._pending
        assert pending is not None
        if now_ms - pending.sent_ms < self.reply_timeout_ms:
            return None
        if pending.tries < self.reply_tries:
            pending.tries += 1
            pending.sent_ms = now_ms
            self.log.append(f"TX {pending.command.mnemonic}")
            return pending.raw
        self.misses += 1
        self._pending = None
        self._phase = "idle"
        if self.misses >= self.miss_limit:
            self.link_lost = True
        self._next_poll_ms = now_ms + self.poll_ms
        return None

    def _accept(self, frame: Frame) -> None:
        """Match a reply to the open sequence and advance the status handshake."""
        pending = self._pending
        if pending is None or frame.sequence != pending.sequence:
            return
        self.log.append(f"RX {_rx_label(frame)}")
        if frame.command is Command.RS:
            self._phase = "saw_rs"
            self._release(pending.sent_ms)
            return
        if frame.command is Command.SND:
            self._status = unpack_status(frame.payload)
            self._phase = "saw_snd"
            self._release(pending.sent_ms)
            return
        if frame.command is Command.ACK:
            self.link_lost = False
            self.misses = 0
            self._phase = "idle"
            self._release(pending.sent_ms)

    def _release(self, sent_ms: int) -> None:
        """Drop the open reply and arm the next idle poll one period later."""
        self._pending = None
        self._next_poll_ms = sent_ms + self.poll_ms


def _rx_label(frame: Frame) -> str:
    """Log ACK with the command it confirms, for example RX ACK AT1."""
    if frame.command is Command.ACK and frame.payload and frame.payload[0] in CODE_TO_COMMAND:
        return f"ACK {CODE_TO_COMMAND[frame.payload[0]].mnemonic}"
    return frame.command.mnemonic


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


_TUNER_ACTION = {
    Command.TUN,
    Command.BYP0,
    Command.BYP1,
    Command.AM0,
    Command.AM1,
    Command.TST0,
    Command.TST1,
    Command.TUP,
    Command.TDN,
    Command.TSC,
    Command.TSL,
    Command.STA,
}


_ANTENNA = {
    Command.AT0: 0,
    Command.AT1: 1,
    Command.AT2: 2,
    Command.AT3: 3,
    Command.AT4: 4,
}


@dataclass(frozen=True)
class Action:
    """A command the remote applies to hardware before it sends ACK."""

    command: Command
    antenna: int | None = None


class RemoteLink:
    """Remote side of the polled link. It transmits only as a reply."""

    def __init__(self) -> None:
        """Start with no cached reply. The first poll will later carry RST RDY."""
        self._buffer = bytearray()
        self._open_sequence: int | None = None
        self._cached: bytes | None = None
        self._cached_sequence: int | None = None
        self._pending_status: bytes | None = None
        self._ready = True
        self.shutdown = False
        self.execute_tuner = False

    def on_bytes(self, data: bytes) -> tuple[bytes | None, Action | None]:
        """Parse one master frame. A duplicate before finish sends nothing."""
        self._buffer.extend(data)
        frames, leftover = decode_frames(bytes(self._buffer))
        self._buffer = bytearray(leftover)
        if not frames:
            return None, None
        return self._on_frame(frames[0])

    def notify_status(self, payload: bytes) -> None:
        """Queue a status payload. The next idle poll offers RS and keeps the bytes."""
        self._pending_status = payload

    def fail(self, command: Command, error: ErrorCode, source: int) -> bytes:
        """Cache an ERR for the open sequence. The sequence number does not change."""
        if self._open_sequence is None:
            raise RuntimeError("no open command to fail")
        raw = encode_frame(
            Frame(
                2,
                1,
                self._open_sequence,
                Command.ERR,
                bytes([int(error), source, command.byte]),
            )
        )
        self._cached = raw
        self._cached_sequence = self._open_sequence
        self._open_sequence = None
        return raw

    def finish(self, action: Action) -> bytes:
        """Cache the ACK for this sequence so a retry can resend it."""
        if self._open_sequence is None:
            raise RuntimeError("no open command to finish")
        raw = encode_frame(
            Frame(2, 1, self._open_sequence, Command.ACK, bytes([action.command.byte]))
        )
        self._cached = raw
        self._cached_sequence = self._open_sequence
        self._open_sequence = None
        return raw

    def _on_frame(self, frame: Frame) -> tuple[bytes | None, Action | None]:
        """Run a new sequence once. The same sequence returns the cached reply."""
        if frame.sequence == self._open_sequence:
            return None, None
        if self._cached is not None and frame.sequence == self._cached_sequence:
            return self._cached, None
        if self.execute_tuner and frame.command in _TUNER_ACTION:
            self._open_sequence = frame.sequence
            return None, Action(frame.command, None)
        if frame.command is Command.RPT:
            cached = self._cached_command()
            if cached is None:
                return self._unavailable(frame), None
            command, payload = cached
            return self._reply(frame, command, payload), None
        if frame.command is Command.STA:
            if self._pending_status is None:
                return self._unavailable(frame), None
            return self._reply(frame, Command.SND, self._pending_status), None
        if frame.command is Command.RST:
            self.shutdown = False
            self._ready = True
            self._open_sequence = frame.sequence
            return None, Action(Command.RST, None)
        if frame.command is Command.F86:
            self.shutdown = True
            self._open_sequence = frame.sequence
            return None, Action(Command.F86, None)
        if frame.command in _ANTENNA:
            if self.shutdown:
                payload = bytes([ErrorCode.FAILED_TO_EXECUTE, 2, frame.command.byte])
                return self._reply(frame, Command.ERR, payload), None
            self._open_sequence = frame.sequence
            return None, Action(frame.command, _ANTENNA[frame.command])
        if frame.command is Command.HHH:
            if self._pending_status is not None:
                return self._reply(frame, Command.RS, b""), None
            if self._ready:
                # Boot and RST announce ready on the idle poll. A queued status
                # still goes out as RS so the reading is not dropped.
                self._ready = False
                return self._reply(frame, Command.RST_RDY, b""), None
            return self._reply(frame, Command.ACK, bytes([Command.HHH.byte])), None
        if frame.command is Command.RR:
            if self._pending_status is not None:
                payload = self._pending_status
                self._pending_status = None
                return self._reply(frame, Command.SND, payload), None
            return self._reply(frame, Command.ACK, bytes([Command.RR.byte])), None
        if frame.command is Command.RCVD:
            return self._reply(frame, Command.ACK, bytes([Command.RCVD.byte])), None
        return None, None

    def _cached_command(self) -> tuple[Command, bytes] | None:
        """Return the command and payload of the last reply, if one exists."""
        if self._cached is None:
            return None
        frames, _leftover = decode_frames(self._cached)
        return frames[0].command, frames[0].payload

    def _unavailable(self, frame: Frame) -> bytes:
        """ERR when RPT or STA has nothing to send. Source is the remote."""
        payload = bytes([ErrorCode.DATA_NOT_AVAILABLE, 2, frame.command.byte])
        return self._reply(frame, Command.ERR, payload)

    def _reply(self, frame: Frame, command: Command, payload: bytes) -> bytes:
        """Send one reply on the sequence the master just used, and cache it."""
        raw = encode_frame(Frame(2, 1, frame.sequence, command, payload))
        self._cached = raw
        self._cached_sequence = frame.sequence
        return raw
