# Remote superloop pieces. Antenna commands land here after the RS485
# frame is accepted. This module drives the latch. It does not import the master.

from dataclasses import dataclass

from common import hal
from common.commands import Command
from common.display import publish
from common.errors import ErrorCode, RelayFault
from common.hal import ByteRing, Flags, drain_rx
from common.buttons import Debouncer, changes
from common.menu import REMOTE_MENU, Menu, render_menu
from common.protocol import Action, Frame, RemoteLink, Status, decode_frames, encode_frame, pack_status
from common.state import LinkState, commit
from remote import config
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


def _sleep(delay_ms: int) -> None:
    """Hold the coil open for the break-before-make delay. The host hook does not wait."""
    hal.sleep_ms(delay_ms)


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
            threshold_w=config.HOT_SWITCH_WATTS,
            enabled=config.HOT_SWITCH_ENABLED,
            stale_ms=config.POWER_STALE_MS,
            delay_ms=config.RELAY_DELAY_MS,
            sleep=_sleep,
        )
    except RelayFault:
        safe_off(latch, "fault")
        state.antenna = 0
        state.relay_mask = 0
        state.banner = "Relay fault"
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
    now_ms: int = 0,
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
        _send_reset(port, mode, fallback, opto, now_ms)
        return link.finish(action)
    if mode == "fallback":
        return _fallback_command(link, action, fallback, opto, now_ms)
    return _serial_command(link, action, port, test_mode, now_ms)


def _send_reset(port: object, mode: str, fallback: Fallback, opto: OptoBank, now_ms: int) -> None:
    """Serial reset is one JSON field. Fallback reset is a short Tune press."""
    if mode == "fallback":
        opto.drive(fallback.press_for(Command.RST), now_ms)
        return
    failed = _emit_tuner(port, b'{"Reset":true}\n', Command.RST, now_ms, None)
    if failed is not None:
        return
    if not hasattr(port, "begin_tuner"):
        return


def _fallback_command(
    link: object, action: Action, fallback: Fallback, opto: OptoBank, now_ms: int
) -> bytes:
    """Press a stock button, or ERR when fallback has no reading to give."""
    presses = fallback.press_for(action.command)
    if presses is ErrorCode.DATA_NOT_AVAILABLE:
        return link.fail(action.command, ErrorCode.DATA_NOT_AVAILABLE, 2)
    opto.drive(presses, now_ms)
    return link.finish(action)


def _emit_tuner(
    port: object, line: bytes, command: Command, now_ms: int, link: object
) -> ErrorCode | None:
    """Hand an encoded line to AtuLink when the port is the remote. Otherwise write it raw."""
    begin = getattr(port, "begin_tuner", None)
    if begin is None:
        port.write(line)
        return None
    sequence = 0 if link is None else (link._open_sequence or 0)
    return begin(line, command, now_ms, sequence)


def _serial_command(
    link: object, action: Action, port: object, test_mode: TestMode, now_ms: int
) -> bytes:
    """Forward one tuner command. Test steps use RelayI and RelayC, not the JSON map."""
    if action.command in (Command.TST0, Command.TST1, Command.TUP, Command.TDN, Command.TSC, Command.TSL):
        line = test_mode.command(action.command)
        if line is None:
            return link.finish(action)
        failed = _emit_tuner(port, line, action.command, now_ms, link)
        if failed is not None:
            return link.fail(action.command, failed, 2)
        if hasattr(port, "atu"):
            port.atu.busy = False
            port.atu._attempt = 0
        return link.finish(action)
    failed = _emit_tuner(port, encode_command(action.command), action.command, now_ms, link)
    if failed is not None:
        return link.fail(action.command, failed, 2)
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


def poll_atu(atu: AtuLink, state: LinkState, link: object, now_ms: int) -> bytes | None:
    """Commit a parsed tuner object once, then offer it on the next idle poll."""
    offline = atu.poll(now_ms)
    if offline is ErrorCode.RESOURCE_OFFLINE:
        return ErrorCode.RESOURCE_OFFLINE
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
                antenna_w=status.antenna_w,
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
    if name == "menu":
        menu.open_menu()
        return
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


class MemoryLatch:
    """Relay latch used by the host loop. The MCP driver replaces it on the Pico."""

    def __init__(self, value: int = 0) -> None:
        """Start from the given coil mask."""
        self.value = value
        self.writes: list[int] = []

    def write(self, value: int) -> None:
        """Record the coil mask."""
        self.writes.append(value)
        self.value = value

    def read(self) -> int:
        """Return the last mask."""
        return self.value


class _Olat:
    """Port bytes for the LED helper."""

    def __init__(self) -> None:
        """Start dark."""
        self.port_a = 0
        self.port_b = 0


class _Panel:
    """Remember the last four lines."""

    def __init__(self) -> None:
        """No lines yet."""
        self.lines = None

    def show_lines(self, lines: tuple[str, str, str, str]) -> None:
        """Store the lines publish just built."""
        self.lines = lines


class RemoteApp:
    """The remote pieces one superloop pass closes over."""

    def __init__(self) -> None:
        """Build rings, the tuner link, and a fresh antenna state."""
        self.link = RemoteLink()
        self.link.execute_tuner = True
        self.rs485 = ByteRing(64)
        self.rs485_flags = Flags()
        self.atu_ring = ByteRing(256)
        self.atu_flags = Flags()
        self.tx = bytearray()
        self.latch = MemoryLatch()
        self.state = LinkState()
        self.port_writes: list[bytes] = []
        self.atu = AtuLink(
            self,
            timeout_ms=config.ATU_TIMEOUT_MS,
            tries=config.ATU_TRIES,
            tune_timeout_ms=config.TUNE_TIMEOUT_MS,
        )
        self.test_mode = TestMode(config.INDUCTOR_COUNT, config.CAPACITOR_COUNT)
        self.fallback = Fallback()
        self.opto = OptoBank()
        self.mode = config.ATU_MODE
        self.now_ms = 0
        self.last_accept_ms = 0
        self.power = PowerView(0.0, 0, 0)
        self.presses: list[str] = []
        self.events: list[str] = []
        self.held: dict[str, bool] = {}
        self.debouncer = Debouncer(hold_ms=30)
        self.menu = Menu(REMOTE_MENU, link_up=True)
        self.menu_highlight = 0
        self.atu_polls = 0
        self.publishes = 0
        self.feeds = 0
        self.mcp_flag = Flags()
        self.gpio_sample: tuple[int, int] | None = None
        self.button_mask = 0xFFFF
        self.shared: dict[str, float | None] = {}
        self.panel = _Panel()
        self.olat = _Olat()

    def begin_tuner(self, line: bytes, command: Command, now_ms: int, sequence: int) -> ErrorCode | None:
        """Start one tuner exchange and remember which RS485 sequence asked for it."""
        self.tuner_sequence = sequence
        self.tuner_command = command
        return self.atu.begin(line, command, now_ms)

    def write(self, data: bytes) -> None:
        """AtuLink uses this as the UART write. UART1 gets the same bytes."""
        self.port_writes.append(data)
        uart = getattr(self, "uart1", None)
        if uart is not None and hasattr(uart, "write"):
            uart.write(data)


def _flush_rs485(app: RemoteApp) -> None:
    """Send the reply bytes once, then drop them so the next pass does not repeat them."""
    uart = getattr(app, "uart0", None)
    if uart is None or not hasattr(uart, "write") or not app.tx:
        return
    uart.write(bytes(app.tx))
    app.tx.clear()


def _power_from_state(app: RemoteApp) -> PowerView:
    """Use the committed forward sample. A missing timestamp is already stale."""
    sample = app.state.power_sample_ms
    if sample is None:
        sample = app.now_ms - config.POWER_STALE_MS
    return PowerView(app.state.forward_w, sample, app.now_ms)


def _remote_drain(app: RemoteApp) -> None:
    """Accept a master frame, or call link loss when the master has been quiet."""
    if app.now_ms - app.last_accept_ms >= config.REMOTE_SILENCE_MS and app.state.link_up:
        on_link_lost(app.state, app.latch)
    data = drain_rx(app.rs485, app.rs485_flags)
    if not data:
        return
    pending = getattr(app, "pending_err", None)
    if pending is not None:
        frames, _leftover = decode_frames(data)
        if frames:
            code, source, command_byte = pending
            app.pending_err = None
            reply = encode_frame(
                Frame(2, 1, frames[0].sequence, Command.ERR, bytes([int(code), source, command_byte]))
            )
            app.last_accept_ms = app.now_ms
            app.state.link_up = True
            if app.state.banner == "Communication Lost":
                app.state.banner = ""
            app.tx.extend(reply)
            _flush_rs485(app)
            return
    power = _power_from_state(app)
    app.power = power
    reply = dispatch_frame(
        data,
        link=app.link,
        latch=app.latch,
        state=app.state,
        power=power,
        port=app,
        mode=app.mode,
        test_mode=app.test_mode,
        fallback=app.fallback,
        opto=app.opto,
        now_ms=app.now_ms,
    )
    if reply is None:
        return
    _copy_optos(app)
    app.last_accept_ms = app.now_ms
    app.state.link_up = True
    if app.state.banner == "Communication Lost":
        app.state.banner = ""
    app.tx.extend(reply)
    _flush_rs485(app)


def encode_err(code: ErrorCode, source: int, command: Command) -> bytes:
    """Build an ERR frame the master can drain. Source 3 is the ATU."""
    return encode_frame(Frame(2, 1, 1, Command.ERR, bytes([int(code), source, command.byte])))


def _remote_poll_atu(app: RemoteApp) -> None:
    """Drain the tuner ring and commit one status. The interrupt does not parse JSON."""
    app.atu_polls += 1
    data = drain_rx(app.atu_ring, app.atu_flags)
    if data:
        app.atu.feed(data)
    err = poll_atu(app.atu, app.state, app.link, app.now_ms)
    if err is not None and app.atu._command is not None:
        app.pending_err = (err, 3, app.atu._command.byte)
        sequence = getattr(app, "tuner_sequence", 0)
        app.tx.extend(
            encode_frame(Frame(2, 1, sequence, Command.ERR, bytes([int(err), 3, app.atu._command.byte])))
        )
    app.power = _power_from_state(app)


def _copy_optos(app: RemoteApp) -> None:
    """Copy GPB4..GPB6 onto the expander. Serial mode does not touch those bits."""
    if app.mode != "fallback":
        return
    chip = getattr(app.latch, "chip", None)
    if chip is None:
        return
    port_a, port_b = chip.read_olat()
    merged = (port_b & ~0x70) | (app.opto.value & 0x70)
    chip.write_olat(port_a, merged)


def _remote_optos(app: RemoteApp) -> None:
    """Drop a fallback opto bit when its press time has elapsed."""
    app.opto.service_optos(app.now_ms)
    _copy_optos(app)


_REMOTE_ALIAS = {
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
    "Select": "select",
    "Menu": "menu",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "select": "select",
}


def _remote_publish(app: RemoteApp) -> None:
    """Draw the menu while it is open, otherwise the tuner screen."""
    app.publishes += 1
    panel = getattr(app, "oled", None) or app.panel
    if app.menu.active:
        labels, highlight = render_menu(app.menu)
        app.menu_highlight = highlight
        padded = (labels + ["", "", "", ""])[:4]
        panel.show_lines((padded[0], padded[1], padded[2], padded[3]))
        write_leds(app.state, app.olat)
        return
    publish_display(app.state, panel, app.olat)


def _remote_buttons(app: RemoteApp) -> None:
    """Debounce a press and run it on this board's tuner and relays."""

    def act(name: str) -> None:
        """Run one debounced remote press on this board's menu and tuner."""
        local: list[str] = []
        remote_on_press(name, app.menu, local)
        app.events.append(name)
        if not local:
            return
        run_menu_handler(
            local[-1],
            app.latch,
            app.state,
            _power_from_state(app),
            app.state.link_up,
            port=app,
            mode=app.mode,
            test_mode=app.test_mode,
            fallback=app.fallback,
            opto=app.opto,
            now_ms=app.now_ms,
        )

    if app.presses:
        raw = app.presses.pop(0)
        act(_REMOTE_ALIAS.get(raw, raw))
        return
    sample = app.gpio_sample
    if sample is not None:
        app.gpio_sample = None
        port_a, _port_b = sample
        current = port_a & 0x1F
        for name, down in changes(app.button_mask, current, config.REMOTE_BUTTONS):
            app.debouncer.sample(_REMOTE_ALIAS.get(name, name), down, app.now_ms)
        app.button_mask = current
    for config_name, down in app.held.items():
        app.debouncer.sample(_REMOTE_ALIAS.get(config_name, config_name), down, app.now_ms)
    for press in app.debouncer.events():
        act(press.name)


def build_remote_tasks(app: RemoteApp) -> list:
    """The remote pass, in order. run_once does not copy this list."""
    return [
        lambda: _remote_drain(app),
        lambda: _remote_poll_atu(app),
        lambda: _remote_optos(app),
        lambda: _remote_publish(app),
        lambda: _remote_buttons(app),
    ]


_HANDLER_COMMAND = {
    "at1": Command.AT1,
    "at2": Command.AT2,
    "at3": Command.AT3,
    "at4": Command.AT4,
    "at0": Command.AT0,
    "tun": Command.TUN,
    "am0": Command.AM0,
    "am1": Command.AM1,
    "byp1": Command.BYP1,
    "byp0": Command.BYP0,
    "tst1": Command.TST1,
    "tst0": Command.TST0,
    "tup": Command.TUP,
    "tdn": Command.TDN,
    "tsc": Command.TSC,
    "tsl": Command.TSL,
    "sta": Command.STA,
    "rst": Command.RST,
}


def run_menu_handler(
    name: str | None,
    latch: object,
    state: LinkState,
    power: PowerView,
    link_up: bool,
    port: object | None = None,
    mode: str = "serial",
    test_mode: TestMode | None = None,
    fallback: Fallback | None = None,
    opto: OptoBank | None = None,
    now_ms: int = 0,
) -> None:
    """Run a remote menu leaf locally. Exit does nothing. Shutdown is not on this menu."""
    del link_up
    if name is None or name == "exit" or name == "f86":
        return
    command = _HANDLER_COMMAND[name]
    if name.startswith("at"):
        apply_from_link(Action(command, int(name[2])), latch, state, power)
        return
    link = RemoteLink()
    frame = encode_frame(Frame(1, 2, 1, command, b""))
    dispatch_frame(
        frame,
        link=link,
        latch=latch,
        state=state,
        power=power,
        port=port if port is not None else bytearray(),
        mode=mode,
        test_mode=test_mode or TestMode(),
        fallback=fallback or Fallback(),
        opto=opto or OptoBank(),
        now_ms=now_ms,
    )


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
