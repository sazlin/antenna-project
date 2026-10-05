from common.state import LinkState, commit, rollback


def test_rollback_returns_the_previous_antenna():
    state = LinkState()
    commit(state, antenna=1, relay_mask=0b0001, led_bits=0b0010, button_mask=0b1000)
    commit(state, antenna=3, relay_mask=0b0100)
    image = rollback(state)
    assert state.antenna == 1
    assert image == {
        "antenna": 1,
        "relay_mask": 0b0001,
        "led_bits": 0b0010,
        "button_mask": 0b1000,
    }
    again = rollback(state)
    assert state.antenna == 1
    assert again == image


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
