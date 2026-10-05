import inspect

import pytest

from common.errors import RelayFault
from common.scheduler import run_once


def test_interrupt_task_runs_four_times():
    order: list[str] = []
    tasks = [
        lambda: order.append("a"),
        lambda: order.append("b"),
        lambda: order.append("c"),
    ]
    run_once(tasks, interrupt=lambda: order.append("isr"), watchdog=lambda: order.append("feed"))
    assert order.count("isr") == 4
    assert order.count("a") == order.count("b") == order.count("c") == 1
    assert order.count("feed") == 1
    assert "time.sleep" not in inspect.getsource(run_once)


def test_task_exception_does_not_stop_the_loop():
    seen: list[str] = []

    def bad() -> None:
        raise RuntimeError("nope")

    errors = run_once([bad, lambda: seen.append("later")], interrupt=lambda: None, watchdog=lambda: None)
    assert seen == ["later"]
    assert isinstance(errors[0], RuntimeError)


def test_relay_fault_escapes():
    def bad() -> None:
        raise RelayFault("coil")

    with pytest.raises(RelayFault):
        run_once([bad], interrupt=lambda: None, watchdog=lambda: None)
