# Master superloop pieces. Button and menu choices become RS485 commands.
# This module does not import the remote and it does not drive a relay.

from common.commands import Command
from common.menu import Menu


def enqueue_menu(menu: Menu, queue: list[Command]) -> str | None:
    """Select the current leaf and queue Tune. Other handlers arrive with the full map."""
    name = menu.select()
    if name == "tun":
        queue.append(Command.TUN)
    return name
