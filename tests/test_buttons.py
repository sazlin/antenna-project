from common.buttons import Debouncer, Press


def test_one_press_after_30_ms():
    box = Debouncer(hold_ms=30)
    box.sample("up", True, 0)
    box.sample("up", True, 29)
    box.sample("up", False, 40)
    assert box.events() == [Press("up")]
    box.sample("up", True, 100)
    box.sample("up", False, 140)
    assert box.events() == [Press("up")]


def test_bounce_shorter_than_hold_is_ignored():
    box = Debouncer(hold_ms=30)
    box.sample("up", True, 0)
    box.sample("up", False, 10)
    assert box.events() == []
