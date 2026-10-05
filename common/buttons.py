# Button edges for both Picos. The expander pins are active low.
# The debouncer sees names and timestamps, so a test does not wait on a clock.

from dataclasses import dataclass


@dataclass(frozen=True)
class Press:
    """One debounced press of a named button."""

    name: str


def changes(previous_mask: int, current_mask: int, names: tuple[str, ...]) -> list[tuple[str, bool]]:
    """Return names whose active-low bit changed. True means the button is down."""
    found: list[tuple[str, bool]] = []
    for index, name in enumerate(names):
        bit = 1 << index
        was_down = (previous_mask & bit) == 0
        is_down = (current_mask & bit) == 0
        if was_down != is_down:
            found.append((name, is_down))
    return found


class Debouncer:
    """Count a press when the button was down for hold_ms before it was released."""

    def __init__(self, hold_ms: int = 30) -> None:
        """Remember how long a contact must stay closed to count."""
        self.hold_ms = hold_ms
        self._since: dict[str, int | None] = {}
        self._pending: list[Press] = []

    def sample(self, name: str, pressed: bool, now_ms: int) -> None:
        """Note one sample. A release after the hold time queues one press."""
        if pressed:
            if self._since.get(name) is None:
                self._since[name] = now_ms
            return
        started = self._since.get(name)
        self._since[name] = None
        if started is not None and now_ms - started >= self.hold_ms:
            self._pending.append(Press(name))

    def events(self) -> list[Press]:
        """Return presses queued since the last call."""
        found = self._pending
        self._pending = []
        return found
