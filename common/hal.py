# Hardware edge for the master and the remote Picos.
# The host tests run on CPython, which has no machine module, so this import
# is caught and machine stays None. UART interrupt handlers may only call
# note_rx_byte. They must not decode frames.

import time

try:
    import machine
except ImportError:
    machine = None

watchdog_ms: int | None = None
_host_ticks_ms = 0
_sleep_hook = lambda _delay_ms: None


def set_host_ticks_ms(now_ms: int) -> None:
    """Set the host clock. The Pico reads time.ticks_ms instead."""
    global _host_ticks_ms
    _host_ticks_ms = now_ms


def set_sleep_hook(hook: object) -> None:
    """Replace the host delay. The Pico calls time.sleep_ms and ignores the hook."""
    global _sleep_hook
    _sleep_hook = hook


def sleep_ms(delay_ms: int) -> None:
    """Wait for a relay coil to release. The host hook defaults to a no-op."""
    if machine is not None and hasattr(time, "sleep_ms"):
        time.sleep_ms(delay_ms)
        return
    _sleep_hook(delay_ms)


def ticks_ms() -> int:
    """Milliseconds since boot. Tasks that tests drive keep the assigned now_ms."""
    if machine is not None:
        return time.ticks_ms()
    return _host_ticks_ms


def bind(module: object) -> None:
    """Install a fake machine for a host test. The real import stays in this file."""
    global machine
    machine = module


def start_watchdog(timeout_ms: int) -> None:
    """Arm the hardware watchdog. On the host, machine is None, so this only records the request."""
    global watchdog_ms
    watchdog_ms = timeout_ms
    if machine is None:
        return
    machine.WDT(timeout=timeout_ms)


class Flags:
    """Flags an interrupt may set. The loop clears them after it drains the data."""

    def __init__(self) -> None:
        """Start with no UART byte and no expander interrupt waiting."""
        self.rx_pending = False
        self.mcp = False


class ByteRing:
    """Fixed bytearray ring. A full push drops the oldest byte and sets overflow."""

    def __init__(self, size: int) -> None:
        """Allocate the storage once. Push and pop do not replace it."""
        self.storage = bytearray(size)
        self._head = 0
        self._tail = 0
        self._count = 0
        self.overflow = False

    def push(self, value: int) -> None:
        """Store one byte. When the ring is full, the oldest byte is discarded."""
        size = len(self.storage)
        if self._count == size:
            self.overflow = True
            self._tail = (self._tail + 1) % size
            self._count -= 1
        self.storage[self._head] = value
        self._head = (self._head + 1) % size
        self._count += 1

    def pop(self) -> int | None:
        """Return the oldest byte, or None when the ring is empty."""
        if self._count == 0:
            return None
        value = self.storage[self._tail]
        self._tail = (self._tail + 1) % len(self.storage)
        self._count -= 1
        return value


def note_rx_byte(ring: ByteRing, flags: Flags, value: int) -> None:
    """Store one UART byte and raise the flag. This is the interrupt path."""
    ring.push(value)
    flags.rx_pending = True


def drain_rx(ring: ByteRing, flags: Flags) -> bytes:
    """Take every stored byte and clear the receive flag."""
    out = bytearray()
    while True:
        value = ring.pop()
        if value is None:
            break
        out.append(value)
    flags.rx_pending = False
    return bytes(out)
