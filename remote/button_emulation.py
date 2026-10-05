# Fallback path when the ATU-100 is still on the stock N7DDC firmware.
# Three optocouplers sit across Tune, Auto, and Bypass. There is no JSON
# and no forward-power sample on this path, so the hot-switch interlock stays off.

from common.commands import Command
from common.errors import ErrorCode

_UNAVAILABLE = {
    Command.TUP,
    Command.TDN,
    Command.TSC,
    Command.TSL,
    Command.TST0,
    Command.TST1,
    Command.STA,
}


class Fallback:
    """Remember Auto and Bypass so a repeated command does not press again."""

    def __init__(self, initial_auto: bool = False, initial_bypass: bool = False) -> None:
        """Power-up is manual and not bypass, matching the stock firmware."""
        self.auto = initial_auto
        self.bypass = initial_bypass

    def press_for(self, command: Command) -> list[tuple[str, int]] | ErrorCode:
        """Return the button and the hold time, or data not available."""
        if command in _UNAVAILABLE:
            return ErrorCode.DATA_NOT_AVAILABLE
        if command is Command.TUN:
            return [("tune", 400)]
        if command is Command.RST:
            return [("tune", 100)]
        if command is Command.AM0:
            return self._toggle("auto", True)
        if command is Command.AM1:
            return self._toggle("auto", False)
        if command is Command.BYP1:
            return self._toggle("bypass", True)
        if command is Command.BYP0:
            return self._toggle("bypass", False)
        return []

    def _toggle(self, name: str, want: bool) -> list[tuple[str, int]]:
        """Press only when the remembered state is different from the request."""
        if getattr(self, name) == want:
            return []
        setattr(self, name, want)
        return [(name, 80)]
