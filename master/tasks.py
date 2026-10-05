# Master superloop pieces. Button and menu choices become RS485 commands.
# This module does not import the remote and it does not drive a relay.

from common.commands import Command
from common.menu import Menu
from common.protocol import MasterLink
from common.state import LinkState, commit


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
