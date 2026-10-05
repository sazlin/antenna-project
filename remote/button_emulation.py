# Fallback path when the ATU-100 is still on the stock N7DDC firmware.
# Three optocouplers sit across Tune, Auto, and Bypass. There is no JSON
# and no forward-power sample on this path, so the hot-switch interlock stays off.

from common.commands import Command
from common.errors import ErrorCode

_OPTO_BIT = {"tune": 1 << 4, "auto": 1 << 5, "bypass": 1 << 6}
_OPTO_MASK = 0x70


class OptoBank:
    """Fallback optocoupler bits on GPB4, GPB5, and GPB6. Levels, not a sleep."""

    def __init__(self) -> None:
        """Start with every optocoupler off."""
        self.value = 0
        self.pressed: list[tuple[str, int]] = []
        self._until: dict[int, int] = {}

    def drive(self, presses: list[tuple[str, int]] | ErrorCode, now_ms: int) -> None:
        """Raise one opto bit for the stock press time. An error presses nothing."""
        if not isinstance(presses, list) or not presses:
            return
        self.pressed.extend(presses)
        name, duration = presses[0]
        bit = _OPTO_BIT[name]
        self.value = (self.value & ~_OPTO_MASK) | bit
        self._until[bit] = now_ms + duration

    def service_optos(self, now_ms: int) -> None:
        """Drop an opto bit once its press time has elapsed."""
        for bit, deadline in list(self._until.items()):
            if now_ms >= deadline:
                self.value &= ~bit
                del self._until[bit]


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
