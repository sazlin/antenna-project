import pytest

from common.display import DisplayBuffer


def test_write_line_and_char():
    panel = DisplayBuffer()
    panel.write_line(1, "100.0W")
    assert panel.line(1) == "100.0W"
    panel.write_char(2, 1, "A")
    assert panel.line(2)[0] == "A"


def test_bad_line_number_is_rejected():
    panel = DisplayBuffer()
    with pytest.raises(ValueError):
        panel.write_line(0, "x")
    with pytest.raises(ValueError):
        panel.write_line(5, "x")


def test_scrollback_drops_the_oldest():
    panel = DisplayBuffer()
    panel.push_scroll("older")
    for index in range(7):
        panel.push_scroll(f"mid{index}")
    panel.push_scroll("newest")
    stored = panel.scroll_lines()
    assert len(stored) == 8
    assert "older" not in stored
    assert stored[-1] == "newest"


def test_highlight_starts_empty():
    panel = DisplayBuffer()
    assert panel.highlight() is None
    panel.set_highlight(3)
    assert panel.highlight() == 3
    with pytest.raises(ValueError):
        panel.set_highlight(0)
