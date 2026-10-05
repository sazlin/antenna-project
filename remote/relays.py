# Antenna relay coils on the remote Pico, through the MCP23017 latch.
# set_antenna is the only place a coil is turned on. force_all_off only
# writes zero. The master never imports this module.

from collections.abc import Callable

from common.errors import RelayFault


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
