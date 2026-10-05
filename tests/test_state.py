from common.state import LinkState, commit


def test_commit_keeps_an_independent_previous():
    state = LinkState()
    assert state.antenna == 0
    assert state.relay_mask == 0
    assert state.led_bits == 0
    assert state.button_mask == 0
    assert state.order == "LC"
    assert state.previous is None
    commit(state, antenna=2, relay_mask=0b0010, led_bits=0b0001, button_mask=0b0100)
    assert state.antenna == 2
    assert state.relay_mask == 0b0010
    assert state.led_bits == 0b0001
    assert state.button_mask == 0b0100
    assert state.previous is not None
    assert state.previous.antenna == 0
    assert state.previous.relay_mask == 0
    commit(state, antenna=4, relay_mask=0b1000)
    assert state.previous.antenna == 2
    assert state.previous.relay_mask == 0b0010
    state.relay_mask = 0
    assert state.previous.relay_mask == 0b0010


def test_commit_stores_lc_order():
    state = LinkState()
    commit(state, order="CL")
    assert state.order == "CL"
    assert state.previous.order == "LC"
