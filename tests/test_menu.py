from common.menu import MASTER_MENU, REMOTE_MENU, Menu


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
