from common.commands import Command
from common.display import publish
from common.menu import MASTER_MENU, REMOTE_MENU, Menu, render_menu
from common.state import LinkState
from master.tasks import master_on_press


class _Panel:
    def __init__(self) -> None:
        self.lines = None

    def show_lines(self, lines: tuple[str, str, str, str]) -> None:
        self.lines = lines


def test_menu_button_draws_the_highlighted_row():
    menu = Menu(MASTER_MENU)
    state = LinkState(
        forward_w=5.0,
        swr=1.15,
        inductance_nh=1250,
        capacitance_pf=150,
        order="LC",
        auto=False,
        bypass=False,
    )
    queue: list[Command] = []
    master_on_press("menu", queue, state, menu)
    assert menu.active is True
    labels, highlight = render_menu(menu)
    assert len(labels) <= 4
    assert all(len(label) <= 16 for label in labels)
    assert labels[highlight] == menu.label
    master_on_press("down", queue, state, menu)
    labels, highlight = render_menu(menu)
    assert labels[highlight] == "Tuner"
    master_on_press("right", queue, state, menu)
    for _ in range(5):
        master_on_press("down", queue, state, menu)
    labels, highlight = render_menu(menu)
    assert len(labels) <= 4
    assert labels[highlight] == menu.label
    master_on_press("left", queue, state, menu)
    while menu.label != "Exit Menu":
        master_on_press("down", queue, state, menu)
    master_on_press("select", queue, state, menu)
    assert menu.active is False
    panel = _Panel()
    publish(state, panel)
    assert panel.lines[1] == "1.15"
    queue.clear()
    master_on_press("tune", queue, state, menu)
    assert queue == [Command.TUN]


def test_remote_select_works_when_link_is_down():
    menu = Menu(REMOTE_MENU, link_up=False)
    labels = [item.label for item in REMOTE_MENU]
    assert "Shutdown" not in labels
    menu.open_menu()
    menu.right()
    menu.down()
    menu.down()
    menu.down()
    assert menu.label == "Antenna 4"
    assert menu.select() == "at4"
    assert menu.link_up is False


def test_select_leaf_exits_with_handler():
    menu = Menu(MASTER_MENU)
    assert menu.label == "Antenna"
    assert menu.active is False
    menu.open_menu()
    menu.right()
    assert menu.label == "Antenna 1"
    assert menu.select() == "at1"
    assert menu.active is False


def test_up_wraps_to_exit_menu():
    menu = Menu(MASTER_MENU)
    menu.open_menu()
    menu.down()
    assert menu.label == "Tuner"
    menu.up()
    menu.up()
    assert menu.label == "Exit Menu"


def test_left_returns_to_the_parent():
    menu = Menu(MASTER_MENU)
    menu.open_menu()
    menu.right()
    menu.left()
    assert menu.label == "Antenna"


def test_exit_menu_returns_exit():
    menu = Menu(MASTER_MENU)
    menu.open_menu()
    menu.up()
    assert menu.label == "Exit Menu"
    assert menu.select() == "exit"


def test_select_on_a_parent_enters_it():
    menu = Menu(MASTER_MENU)
    menu.open_menu()
    assert menu.select() is None
    assert menu.label == "Antenna 1"


def test_shutdown_returns_f86():
    menu = Menu(MASTER_MENU)
    menu.open_menu()
    menu.down()
    menu.down()
    assert menu.label == "Shutdown"
    assert menu.select() == "f86"
