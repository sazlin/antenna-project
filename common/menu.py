# Five-button menus for the master and the remote.
# The tree is data. Selecting a leaf exits the menu and returns a handler name.
# The remote can do this while the RS485 link is down.

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    """One menu row. A parent has children and no handler."""

    label: str
    handler: str | None = None
    children: tuple["MenuItem", ...] = ()


def _item(label: str, handler: str) -> MenuItem:
    """Build a leaf the operator can select."""
    return MenuItem(label, handler)


_ANTENNA = MenuItem(
    "Antenna",
    None,
    (
        _item("Antenna 1", "at1"),
        _item("Antenna 2", "at2"),
        _item("Antenna 3", "at3"),
        _item("Antenna 4", "at4"),
        _item("All off", "at0"),
    ),
)
_TUNER = MenuItem(
    "Tuner",
    None,
    (
        _item("Tune", "tun"),
        _item("Auto", "am0"),
        _item("Manual", "am1"),
        _item("Bypass on", "byp1"),
        _item("Bypass off", "byp0"),
        _item("Test on", "tst1"),
        _item("Test off", "tst0"),
        _item("Step up", "tup"),
        _item("Step down", "tdn"),
        _item("Select C", "tsc"),
        _item("Select L", "tsl"),
        _item("Status", "sta"),
        _item("Reset tuner", "rst"),
    ),
)
MASTER_MENU = (
    _ANTENNA,
    _TUNER,
    _item("Shutdown", "f86"),
    _item("Exit Menu", "exit"),
)
REMOTE_MENU = (_ANTENNA, _TUNER, _item("Exit Menu", "exit"))


class Menu:
    """Up, down, left, right, and select over one menu tree."""

    def __init__(self, items: tuple[MenuItem, ...], link_up: bool = True) -> None:
        """Start on the first label, closed, until open_menu."""
        self.items = items
        self.link_up = link_up
        self.active = False
        self._rows = items
        self._index = 0
        self._stack: list[tuple[tuple[MenuItem, ...], int]] = []

    @property
    def label(self) -> str:
        """Return the label the highlight is on."""
        return self._rows[self._index].label

    def open_menu(self) -> None:
        """Show the top level. The first row is Antenna."""
        self.active = True
        self._rows = self.items
        self._index = 0
        self._stack = []

    def down(self) -> None:
        """Move to the next row, wrapping to the top."""
        self._index = (self._index + 1) % len(self._rows)

    def up(self) -> None:
        """Move to the previous row, wrapping to the bottom."""
        self._index = (self._index - 1) % len(self._rows)

    def right(self) -> None:
        """Enter the child list when this row has one."""
        self._enter()

    def left(self) -> None:
        """Return to the parent row."""
        if not self._stack:
            return
        self._rows, self._index = self._stack.pop()

    def select(self) -> str | None:
        """Enter a parent, or return a leaf handler and close the menu."""
        item = self._rows[self._index]
        if item.children:
            self._enter()
            return None
        self.active = False
        return item.handler

    def _enter(self) -> None:
        """Push the current row and show its children."""
        item = self._rows[self._index]
        if not item.children:
            return
        self._stack.append((self._rows, self._index))
        self._rows = item.children
        self._index = 0
