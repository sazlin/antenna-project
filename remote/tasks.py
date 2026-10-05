# Remote superloop pieces. Antenna commands land here after the RS485
# frame is accepted. This module drives the latch. It does not import the master.

from dataclasses import dataclass

from common.commands import Command
from common.display import publish
from common.errors import ErrorCode, RelayFault
from common.menu import Menu
from common.protocol import Action, Status, pack_status
from common.state import LinkState, commit
from remote.atu_link import AtuLink, TestMode, encode_command
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


def drain_rs485(
    link: object,
    rx: bytearray,
    latch: object,
    state: LinkState,
    power: PowerView,
    port: object,
    test_mode: TestMode,
    fallback: Fallback,
    opto: OptoBank,
) -> bytes | None:
    """Take one master frame off the queue and run it. The caller sends the reply."""
    if not rx:
        return None
    data = bytes(rx)
    rx.clear()
    reply = dispatch_frame(
        data,
        link=link,
        latch=latch,
        state=state,
        power=power,
        port=port,
        mode="serial",
        test_mode=test_mode,
        fallback=fallback,
        opto=opto,
    )
    return reply


def poll_atu(atu: AtuLink, state: LinkState, link: object, now_ms: int) -> None:
    """Commit a parsed tuner object once, then offer it on the next idle poll."""
    atu.poll(now_ms)
    status = atu.last_status
    if status is None or atu._announced:
        return
    atu._announced = True
    commit(
        state,
        forward_w=status.forward_w,
        antenna_w=status.antenna_w,
        swr=status.swr,
        inductance_nh=status.inductance_nh,
        capacitance_pf=status.capacitance_pf,
        efficiency_pct=status.efficiency_pct,
        auto=bool(status.auto),
        bypass=bool(status.bypass),
        order=status.order or "LC",
        power_sample_ms=now_ms,
    )
    link.notify_status(
        pack_status(
            Status(
                auto=bool(status.auto),
                bypass=bool(status.bypass),
                atu_link=True,
                test_mode=False,
                efficiency_valid=status.efficiency_pct is not None,
                power_valid=status.forward_w is not None,
                order=status.order or "LC",
                forward_w=status.forward_w or 0.0,
                swr=status.swr or 0.0,
                inductance_nh=status.inductance_nh or 0,
                capacitance_pf=status.capacitance_pf or 0,
                efficiency_pct=status.efficiency_pct or 0,
                antenna=state.antenna,
                error_code=0,
                error_source=0,
            )
        )
    )


def _set_bit(value: int, bit: int, on: bool) -> int:
    """Turn one LED bit on or off and leave the other bits alone."""
    mask = 1 << bit
    if on:
        return value | mask
    return value & ~mask


def write_leds(state: LinkState, olat: object) -> None:
    """Drive GPA5 Link OK and GPA6 Error. Relay bits on port B are not touched."""
    error = not state.link_up or bool(state.banner)
    olat.port_a = _set_bit(olat.port_a, 5, state.link_up)
    olat.port_a = _set_bit(olat.port_a, 6, error)


def remote_on_press(name: str, menu: Menu, local_queue: list[str]) -> None:
    """Navigate the local menu. Select still returns a handler when the master is quiet."""
    if name == "select":
        handler = menu.select()
        if handler and handler != "exit":
            local_queue.append(handler)
        return
    if menu.active and name in ("up", "down", "left", "right"):
        getattr(menu, name)()


def publish_display(state: LinkState, panel: object, olat: object | None = None) -> None:
    """Draw the current row and the remote LEDs. Link loss has already set the banner."""
    publish(state, panel)
    if olat is not None:
        write_leds(state, olat)


def on_link_lost(state: LinkState, latch: object) -> None:
    """Keep the selected antenna. The latch is not written when the master goes quiet."""
    del latch
    state.banner = "Communication Lost"
    state.link_up = False


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
