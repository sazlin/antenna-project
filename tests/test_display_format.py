from common.display import Reading, format_capacitance_pf, format_inductance_nh, format_power, format_swr, screen_lines


def _reading(**overrides: object) -> Reading:
    values = {
        "forward_w": 100.0,
        "swr": 1.15,
        "inductance_nh": 1250,
        "capacitance_pf": 150,
        "auto": True,
        "bypass": False,
        "order": "LC",
        "efficiency": None,
        "antenna_w": None,
    }
    values.update(overrides)
    return Reading(**values)


def test_efficiency_screen_at_one_watt():
    lines = screen_lines(_reading(antenna_w=99.0, efficiency=99))
    assert lines == ("100.0W         .", "1.15", "99.0W", "99%")
    low = screen_lines(_reading(forward_w=1.0, antenna_w=0.5, efficiency=99))
    assert low[2] == "0.5W"
    assert low[3] == "99%"


def test_efficiency_hidden_below_one_watt():
    lines = screen_lines(_reading(forward_w=0.9, antenna_w=0.5, efficiency=99))
    assert lines[2] == "1.25uH"
    assert lines[3] == "150pF"
    missing = screen_lines(_reading(forward_w=100.0, efficiency=None, antenna_w=99.0))
    assert missing[2] == "1.25uH"


def test_efficiency_capped_at_99():
    lines = screen_lines(_reading(antenna_w=100.0, efficiency=100))
    assert lines[2] == "100.0W"
    assert lines[3] == "99%"


def test_auto_marker_and_lc_order():
    lines = screen_lines(_reading())
    assert lines[0] == "100.0W         ."
    assert len(lines[0]) == 16
    assert lines[0][-1] == "."
    assert lines[1] == "1.15"
    assert lines[2] == "1.25uH"
    assert lines[3] == "150pF"


def test_bypass_marker_wins():
    lines = screen_lines(_reading(auto=True, bypass=True))
    assert lines[0].endswith("_")
    assert len(lines[0]) == 16


def test_cl_swaps_l_and_c():
    lines = screen_lines(_reading(order="CL", auto=False))
    assert lines[2] == "150pF"
    assert lines[3] == "1.25uH"
    assert lines[0].endswith(" ")


def test_nanohenries_become_microhenries():
    assert format_inductance_nh(1250) == "1.25uH"
    assert format_inductance_nh(50) == "0.05uH"


def test_picofarads():
    assert format_capacitance_pf(150) == "150pF"
    assert format_capacitance_pf(0) == "0pF"


def test_power_one_decimal():
    assert format_power(100) == "100.0W"
    assert format_power(5) == "5.0W"
    assert format_power(0.1) == "0.1W"


def test_swr_two_decimals():
    assert format_swr(1.15) == "1.15"
    assert format_swr(1) == "1.00"
