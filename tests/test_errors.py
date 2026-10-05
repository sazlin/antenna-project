from common.errors import ErrorCode, banner, make_error, propagate


def test_error_keeps_source_and_nature():
    fault = make_error(ErrorCode.DATA_CORRUPTED, source="atu")
    assert fault.nature == "Data Corrupted"
    assert fault.source == "atu"
    wrapped = propagate([fault])
    assert wrapped.nature == "Data Corrupted"
    assert wrapped.path == ("atu", "remote", "master")
    local = make_error(ErrorCode.FAILED_TO_EXECUTE, source="remote")
    assert local.local is True
    lost = make_error(ErrorCode.COMMUNICATION_LOST, source="master")
    assert lost.system is True
    assert banner(lost) == "Communication Lost"
    assert banner(make_error(ErrorCode.HOT_SWITCH, source="remote")) == "Hot switch"
    assert banner(make_error(ErrorCode.RELAY_FAULT, source="remote")) == "Relay fault"
    assert ErrorCode.RESOURCE_OFFLINE.code == 3
    natures = {code.nature for code in ErrorCode}
    for text in (
        "Failed to Execute Command",
        "Data Not Available",
        "Resource offline",
        "Communication Lost",
        "Data Corrupted",
    ):
        assert text in natures
