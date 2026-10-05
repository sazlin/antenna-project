# Antenna relay coils on the remote Pico, through the MCP23017 latch.
# set_antenna is the only place a coil is turned on. force_all_off only
# writes zero. The master never imports this module.

from collections.abc import Callable

from common.errors import ErrorCode, RelayFault
from common.state import LinkState


def apply_antenna_command(
    latch: object,
    state: LinkState,
    *,
    target: int,
    now_ms: int,
    forward_w: float | None,
    sample_ms: int,
    threshold_w: float,
    enabled: bool,
    stale_ms: int,
    delay_ms: int,
    sleep: Callable[[int], None],
) -> ErrorCode | None:
    """Select an antenna. The coil stays closed when that antenna is already on it."""
    bit = 0 if target == 0 else 1 << (target - 1)
    if state.antenna == target and latch.read() == bit:
        return None
    fresh = forward_w is not None and now_ms - sample_ms < stale_ms
    if enabled and fresh and forward_w > threshold_w:
        return ErrorCode.HOT_SWITCH
    set_antenna(latch, target, delay_ms, sleep)
    return None


def set_antenna(latch: object, target: int, delay_ms: int, sleep: Callable[[int], None]) -> None:
    """Energize one antenna, or none. This is the only place a coil is turned on.

    The coil releases through a flyback diode, so the open state is held for
    delay_ms before another coil may close. Two bits, or a readback that does
    not match the write, opens every coil and raises RelayFault.
    """
    if target not in (0, 1, 2, 3, 4):
        raise ValueError(f"antenna {target} is not 0..4")
    current = latch.read()
    if bin(current).count("1") > 1:
        latch.write(0)
        raise RelayFault("latch already has more than one coil")
    latch.write(0)
    if latch.read() != 0:
        latch.write(0)
        raise RelayFault("all-off readback was not zero")
    sleep(delay_ms)
    if target == 0:
        return
    bit = 1 << (target - 1)
    latch.write(bit)
    if latch.read() != bit:
        latch.write(0)
        raise RelayFault("coil readback did not match the write")
