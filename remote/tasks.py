# Remote superloop pieces. Antenna commands land here after the RS485
# frame is accepted. This module drives the latch. It does not import the master.

from dataclasses import dataclass

from common.commands import Command
from common.errors import ErrorCode, RelayFault
from common.protocol import Action
from common.state import LinkState, commit
from remote.atu_link import TestMode, encode_command
from remote.button_emulation import Fallback, OptoBank
from remote.relays import apply_antenna_command, safe_off


@dataclass
class PowerView:
    """The forward-power sample the interlock is allowed to see."""

    forward_w: float | None
    sample_ms: int
    now_ms: int


@dataclass
class ApplyReply:
    """Ack after the coil moved, or the error that stopped the move."""

    kind: str
    code: ErrorCode | None = None


def _sleep(_delay_ms: int) -> None:
    """The host test must not wait out the relay flyback."""


def apply_from_link(action: Action, latch: object, state: LinkState, power: PowerView) -> ApplyReply:
    """Move the coil, then commit. A fault opens every coil and does not restore the old mask."""
    target = 0 if action.antenna is None else action.antenna
    try:
        result = apply_antenna_command(
            latch,
            state,
            target=target,
            now_ms=power.now_ms,
            forward_w=power.forward_w,
            sample_ms=power.sample_ms,
            threshold_w=1.0,
            enabled=True,
            stale_ms=1000,
            delay_ms=100,
            sleep=_sleep,
        )
    except RelayFault:
        safe_off(latch, "fault")
        state.antenna = 0
        state.relay_mask = 0
        return ApplyReply("err", ErrorCode.RELAY_FAULT)
    if result is not None:
        return ApplyReply("err", result)
    mask = 0 if target == 0 else 1 << (target - 1)
    commit(state, antenna=target, relay_mask=mask)
    return ApplyReply("ack")


def _finish_or_fail(link: object, action: Action, reply: ApplyReply) -> bytes:
    """ACK only after the coil move. A refusal is an ERR and not an ACK."""
    if reply.kind == "ack":
        return link.finish(action)
    return link.fail(action.command, reply.code, 2)


def _clear_coils(latch: object, state: LinkState, reason: str) -> None:
    """Open every coil and remember that in the current row, not the previous one."""
    safe_off(latch, reason)
    state.antenna = 0
    state.relay_mask = 0


def dispatch_frame(
    data: bytes,
    *,
    link: object,
    latch: object,
    state: LinkState,
    power: PowerView,
    port: object,
    mode: str,
    test_mode: TestMode,
    fallback: Fallback,
    opto: OptoBank,
) -> bytes | None:
    """Run one master frame on the hardware, then ACK or ERR."""
    link.execute_tuner = True
    _immediate, action = link.on_bytes(data)
    if action is None:
        return _immediate
    command = action.command
    if command in (Command.AT0, Command.AT1, Command.AT2, Command.AT3, Command.AT4):
        return _finish_or_fail(link, action, apply_from_link(action, latch, state, power))
    if command is Command.F86:
        _clear_coils(latch, state, "F86")
        return link.finish(action)
    if command is Command.RST:
        _clear_coils(latch, state, "reset")
        _send_reset(port, mode, fallback, opto)
        return link.finish(action)
    if mode == "fallback":
        return _fallback_command(link, action, fallback, opto)
    return _serial_command(link, action, port, test_mode)


def _send_reset(port: object, mode: str, fallback: Fallback, opto: OptoBank) -> None:
    """Serial reset is one JSON field. Fallback reset is a short Tune press."""
    if mode == "fallback":
        opto.drive(fallback.press_for(Command.RST), 0)
        return
    port.write(b'{"Reset":true}\n')


def _fallback_command(link: object, action: Action, fallback: Fallback, opto: OptoBank) -> bytes:
    """Press a stock button, or ERR when fallback has no reading to give."""
    presses = fallback.press_for(action.command)
    if presses is ErrorCode.DATA_NOT_AVAILABLE:
        return link.fail(action.command, ErrorCode.DATA_NOT_AVAILABLE, 2)
    opto.drive(presses, 0)
    return link.finish(action)


def _serial_command(link: object, action: Action, port: object, test_mode: TestMode) -> bytes:
    """Forward one tuner command. Test steps use RelayI and RelayC, not the JSON map."""
    if action.command in (Command.TST0, Command.TST1, Command.TUP, Command.TDN, Command.TSC, Command.TSL):
        line = test_mode.command(action.command)
        if line is not None:
            port.write(line)
        return link.finish(action)
    port.write(encode_command(action.command))
    return link.finish(action)


def apply_menu(
    handler: str | None,
    latch: object,
    state: LinkState,
    power: PowerView,
    link_up: bool,
    tx: bytearray,
) -> None:
    """Run a remote menu leaf on the local latch. The master is not polled."""
    del link_up, tx
    if handler == "at4":
        apply_from_link(Action(Command.AT4, 4), latch, state, power)
