# Master superloop pieces. Button and menu choices become RS485 commands.
# This module does not import the remote and it does not drive a relay.

from common.commands import Command
from common.display import publish
from common.errors import ErrorCode
from common.hal import ByteRing, Flags, drain_rx
from common.menu import Menu
from common.protocol import MasterLink
from common.state import LinkState, commit
from master import config as master_config


def _set_bit(value: int, bit: int, on: bool) -> int:
    """Turn one LED bit on or off and leave the other bits alone."""
    mask = 1 << bit
    if on:
        return value | mask
    return value & ~mask


def leds_for(*, link_up: bool, fault: bool, auto: bool, bypass: bool, rf: bool) -> dict[str, bool]:
    """Five master LED meanings. The names match the front panel."""
    return {"link_ok": link_up, "error": fault, "auto": auto, "bypass": bypass, "rf": rf}


def write_leds(state: LinkState, olat: object) -> None:
    """Drive GPB2..GPB6. RF Present is on only above 1.0 W forward."""
    flags = leds_for(
        link_up=state.link_up,
        fault=not state.link_up or bool(state.banner),
        auto=state.auto,
        bypass=state.bypass,
        rf=state.forward_w is not None and state.forward_w > 1.0,
    )
    port = olat.port_b
    port = _set_bit(port, 2, flags["link_ok"])
    port = _set_bit(port, 3, flags["error"])
    port = _set_bit(port, 4, flags["auto"])
    port = _set_bit(port, 5, flags["bypass"])
    port = _set_bit(port, 6, flags["rf"])
    olat.port_b = port


def master_on_press(name: str, queue: list[Command], state: LinkState, menu: Menu) -> None:
    """Menu keys navigate while the menu is open. The other keys queue a command."""
    if name == "menu":
        menu.open_menu()
        return
    if menu.active and name in ("up", "down", "left", "right", "select"):
        getattr(menu, name)()
        return
    if name == "tune":
        queue.append(Command.TUN)
        return
    if name == "antenna":
        nxt = 1 if state.antenna >= 4 or state.antenna < 1 else state.antenna + 1
        queue.append((Command.AT1, Command.AT2, Command.AT3, Command.AT4)[nxt - 1])
        return
    if name == "bypass":
        queue.append(Command.BYP0 if state.bypass else Command.BYP1)
        return
    if name == "am":
        queue.append(Command.AM1 if state.auto else Command.AM0)


def publish_display(state: LinkState, panel: object, olat: object | None = None) -> None:
    """Draw the screen and, when the latch is present, the master LEDs."""
    publish(state, panel)
    if olat is not None:
        write_leds(state, olat)


def on_link_lost(state: LinkState, outbound: list[Command]) -> None:
    """Show the banner. Do not queue an antenna command because the link dropped."""
    del outbound
    state.banner = "Communication Lost"
    state.link_up = False


def maybe_poll(link: MasterLink, now_ms: int, tx: bytearray) -> None:
    """Send the next master frame into tx. This is the only RS485 sender."""
    raw = link.poll(now_ms)
    if raw:
        tx.extend(raw)


def drain_rs485(link: MasterLink, rx: bytearray, state: LinkState, antenna_w: float | None = None) -> None:
    """Read remote frames. A SND updates the master row, including antenna watts when known."""
    if not rx:
        return
    data = bytes(rx)
    rx.clear()
    link.feed(data)
    reading = link.status()
    if reading is None:
        return
    commit(
        state,
        forward_w=reading.forward_w,
        swr=reading.swr,
        inductance_nh=reading.inductance_nh,
        capacitance_pf=reading.capacitance_pf,
        efficiency_pct=reading.efficiency_pct if reading.efficiency_valid else None,
        antenna_w=antenna_w if reading.efficiency_valid else None,
        auto=reading.auto,
        bypass=reading.bypass,
        order=reading.order,
        antenna=reading.antenna,
        link_up=True,
        banner="",
    )


class MasterApp:
    """The master pieces one superloop pass closes over."""

    def __init__(self) -> None:
        """Build the poller from the current config values."""
        self.link = MasterLink(
            poll_ms=master_config.POLL_MS,
            reply_timeout_ms=master_config.REPLY_TIMEOUT_MS,
            reply_tries=master_config.REPLY_TRIES,
            miss_limit=master_config.MISS_LIMIT,
        )
        self.rs485 = ByteRing(64)
        self.rs485_flags = Flags()
        self.tx = bytearray()
        self.state = LinkState()
        self.now_ms = 0
        self.presses: list[str] = []
        self.events: list[str] = []
        self.publishes = 0
        self.shared: dict[str, float | None] = {}
        self.panel = type("Panel", (), {"lines": None, "show_lines": lambda self, lines: setattr(self, "lines", lines)})()
        self.olat = type("Olat", (), {"port_a": 0, "port_b": 0})()
        self._announced_loss = False

    def note_loss(self) -> None:
        """Banner only. A lost poll does not move an antenna."""
        if self._announced_loss:
            return
        self._announced_loss = True
        on_link_lost(self.state, [])


def _apply_err(app: MasterApp) -> None:
    """An ERR from the remote sets the banner and the Error LED."""
    frame = app.link.last_err
    if frame is None or not frame.payload:
        return
    app.state.banner = ErrorCode(frame.payload[0]).nature
    write_leds(app.state, app.olat)
    app.link.last_err = None


def _master_drain(app: MasterApp) -> None:
    """Read one remote reply into the master row."""
    data = drain_rx(app.rs485, app.rs485_flags)
    if not data:
        return
    buf = bytearray(data)
    drain_rs485(app.link, buf, app.state, app.shared.get("antenna_w"))
    _apply_err(app)


def _master_poll(app: MasterApp) -> None:
    """Send the queued command or HHH. Link loss only sets the banner."""
    maybe_poll(app.link, app.now_ms, app.tx)
    if app.link.link_lost:
        app.note_loss()


def _master_publish(app: MasterApp) -> None:
    """Draw the master screen and LEDs."""
    app.publishes += 1
    publish_display(app.state, app.panel, app.olat)


def _master_buttons(app: MasterApp) -> None:
    """Turn one debounced press into one sampled event."""
    if app.presses:
        app.events.append(app.presses.pop(0))


def build_master_tasks(app: MasterApp) -> list:
    """The master pass. maybe_poll is the only RS485 sender."""
    return [
        lambda: _master_drain(app),
        lambda: _master_poll(app),
        lambda: _master_publish(app),
        lambda: _master_buttons(app),
    ]


_HANDLER = {
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
    "f86": Command.F86,
}


def queue_handler(name: str | None, queue: list[Command]) -> None:
    """Queue one menu leaf. Exit runs no command."""
    if name is None or name == "exit":
        return
    queue.append(_HANDLER[name])


def enqueue_menu(menu: Menu, queue: list[Command]) -> str | None:
    """Select the current leaf and queue its command."""
    name = menu.select()
    queue_handler(name, queue)
    return name
