from common.display import format_capacitance_pf, format_inductance_nh, format_power, format_swr


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
