import sys

from common.hal import ByteRing, Flags, drain_rx, note_rx_byte


def test_ring_drops_oldest_when_full():
    ring = ByteRing(8)
    ring.push(1)
    ring.push(2)
    ring.push(3)
    assert [ring.pop(), ring.pop(), ring.pop()] == [1, 2, 3]
    full = ByteRing(8)
    assert isinstance(full.storage, bytearray)
    assert len(full.storage) == 8
    for value in range(8):
        full.push(value)
    full.push(9)
    assert full.overflow is True
    assert isinstance(full.storage, bytearray)
    assert len(full.storage) == 8
    assert full.pop() == 1


def test_isr_only_sets_the_flag_and_stores_the_byte():
    sys.modules.pop("machine", None)
    assert "machine" not in sys.modules
    ring = ByteRing(8)
    flags = Flags()
    note_rx_byte(ring, flags, 0x41)
    assert flags.rx_pending is True
    assert drain_rx(ring, flags) == b"A"
    assert flags.rx_pending is False
    source = open("common/hal.py", encoding="utf-8").read()
    assert "decode_frames" not in source
