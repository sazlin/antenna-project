# Cooperative loop shared by the master and the remote.
# Each pass runs the interrupt hook four times, then each short task once,
# then feeds the watchdog. Tasks must not block. There is no uasyncio.

from collections.abc import Callable

from common.errors import RelayFault


def run_once(
    tasks: list[Callable[[], None]],
    interrupt: Callable[[], None],
    watchdog: Callable[[], None],
) -> list[BaseException]:
    """Run one superloop pass. RelayFault stops the pass. Other errors do not."""
    errors: list[BaseException] = []
    for _ in range(4):
        interrupt()
    for task in tasks:
        try:
            task()
        except RelayFault as exc:
            errors.append(exc)
            raise
        except Exception as exc:
            errors.append(exc)
    watchdog()
    return errors
