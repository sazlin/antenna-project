import master.config as master_config
import remote.config as remote_config

_SHARED = (
    "I2C_SDA",
    "I2C_SCL",
    "RS485_TX",
    "RS485_RX",
    "RS485_BAUD",
    "ATU_TX",
    "ATU_RX",
    "ATU_BAUD",
    "MCP_INTA",
    "MCP_INTB",
    "OLED_ADDR",
    "MCP23017_ADDR",
)

_FORBIDDEN = {23, 24, 25, 29}


def _integers(module: object) -> set[int]:
    return {value for value in vars(module).values() if isinstance(value, int)}


def test_shared_pins_match_and_wireless_gpios_are_free():
    for name in _SHARED:
        assert getattr(master_config, name) == getattr(remote_config, name)
    assert _FORBIDDEN.isdisjoint(_integers(master_config))
    assert _FORBIDDEN.isdisjoint(_integers(remote_config))
    assert remote_config.OLED_ADDR == 0x3C
    assert remote_config.MCP23017_ADDR == 0x20
    assert remote_config.ATU_BAUD == 4800
    assert remote_config.RS485_BAUD == 115200
    assert remote_config.ATU_MODE == "serial"


def test_timeouts_and_button_names():
    assert remote_config.RELAY_DELAY_MS == 100
    assert remote_config.HOT_SWITCH_WATTS == 1.0
    assert remote_config.HOT_SWITCH_ENABLED is True
    assert remote_config.POLL_MS == 200
    assert remote_config.REPLY_TIMEOUT_MS == 500
    assert remote_config.REPLY_TRIES == 3
    assert remote_config.MISS_LIMIT == 5
    assert remote_config.ATU_TIMEOUT_MS == 500
    assert remote_config.ATU_TRIES == 3
    assert remote_config.TUNE_TIMEOUT_MS == 30000
    assert remote_config.POWER_STALE_MS == 1000
    assert remote_config.INDUCTOR_COUNT == 7
    assert remote_config.CAPACITOR_COUNT == 7
    assert remote_config.WATCHDOG_MS == 3000
    assert remote_config.REMOTE_SILENCE_MS == 2000
    assert master_config.MASTER_BUTTONS == (
        "Up",
        "Down",
        "Left",
        "Right",
        "Select",
        "Tune",
        "A/M",
        "Bypass",
        "Antenna Select",
        "Menu",
    )
    assert remote_config.REMOTE_BUTTONS == ("Up", "Down", "Left", "Right", "Select")
