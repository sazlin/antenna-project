from common.display import format_power, format_swr


def test_power_one_decimal():
    assert format_power(100) == "100.0W"
    assert format_power(5) == "5.0W"
    assert format_power(0.1) == "0.1W"


def test_swr_two_decimals():
    assert format_swr(1.15) == "1.15"
    assert format_swr(1) == "1.00"
