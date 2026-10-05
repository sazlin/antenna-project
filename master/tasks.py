# Master superloop pieces. Button and menu choices become RS485 commands.
# This module does not import the remote and it does not drive a relay.

from common.commands import Command
from common.display import publish
from common.menu import Menu
from common.protocol import MasterLink
from common.state import LinkState, commit


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


def enqueue_menu(menu: Menu, queue: list[Command]) -> str | None:
    """Select the current leaf and queue Tune. Other handlers arrive with the full map."""
    name = menu.select()
    if name == "tun":
        queue.append(Command.TUN)
    return name
