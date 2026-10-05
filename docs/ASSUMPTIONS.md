# Assumptions

These are the choices the client can confirm or override. The eight decisions come first. The engineering choices follow, each with the config name or the document section that changes it.

## Client decisions

1. Hot-switch protection. Refuse an antenna change while the ATU-100 reports more than 1 W forward. Threshold and enable live in config. The check runs only when the serial link is reporting power.

2. On RS485 link loss, Keep the current antenna. Show Communication Lost on both displays. Do not drop a relay because the master went quiet.

3. ATU-100 link is the ukoda/ATU-100-remote serial firmware, not RA6/RA7 bit-bang. MPLAB X and XC8. The client has a PICkit 3 or similar.

4. Test mode is direct L/C relay commands from the remote. TST0/TST1, TUP, TDN, TSC, and TSL. No ATU-100 power cycle.

5. Master buttons: Up, Down, Left, Right, Select, Tune, A/M, Bypass, Antenna Select, Menu. Master LEDs: Link OK, Error, Auto Mode, Bypass, RF Present. Map in `master/config.py`.

6. Remote buttons: 5 buttons, Up, Down, Left, Right, Select. Remote LEDs: Link OK, Error. Map in `remote/config.py`.

7. Break-before-make delay 100 ms, configurable.

8. Identical Pico pin assignments on both boards. Never GPIO 23, 24, 25 or 29.

## Engineering assumptions

A1. The RS485 frame is the byte layout in `docs/PROTOCOL.md`. Change it only in `common/protocol.py` and `docs/PROTOCOL.md` together. Baud is `RS485_BAUD` (115200 8N1). The U094 has no DE pin. Do not assign a direction GPIO.

A2. CRC is CRC-16/CCITT-FALSE, polynomial 0x1021, init 0xFFFF, no reflection, xorout 0. The on-wire CRC is little-endian.

A3. Master reply timeout is `REPLY_TIMEOUT_MS` (500). A new command is sent at most `REPLY_TRIES` (3) times, counting the first send. Five missed polls (`MISS_LIMIT`) set link loss on the master. Poll period is `POLL_MS` (200) when the master is idle. The remote uses a separate silence timer, `REMOTE_SILENCE_MS` (2000), counted from the last accepted frame. 2000 is greater than 500 so one outstanding reply wait is not silence. Change the remote timer in `remote/config.py`. The master miss counter stays in `common/protocol.py`.

A4. `set_antenna` is the only function that turns a relay coil on. `force_all_off` only writes zero. F86, boot, reset, and watchdog use `force_all_off` and ignore the hot-switch interlock. AT0 through AT4 go through `apply_antenna_command`, which checks the interlock first. A display or menu exception does not drop relays. `RelayFault` does.

A5. Reporting power means a forward-power sample whose age is under `POWER_STALE_MS` (1000). The sample is the `Forward` field from A12. A stale sample, fallback mode, `forward_w` is None, or a status that has efficiency but no `Forward` does not block an antenna change. Refusal is strict greater-than `HOT_SWITCH_WATTS` (1.0). 1.0 W is allowed. Antenna watts are never compared with the threshold.

A6. Asking for the antenna that is already selected does not open the coil.

A7. ukoda `main.c` sends numbers with one decimal place when EEPROM high-power mode is off. A one-line fork is still required, for the reason in A12. `atu100_firmware/README.md` records the pinned upstream hex, the unified diff, and the build steps. The host suite does not compile XC8. The wire key for efficiency is `efficency` in the C source. Also accept `Efficency`.

A8. RST sends `{"Reset":true}` and does not send `{"x":true}`. The `x` name resets the PIC as soon as the closing quote arrives. `docs/ATU_LINK.md` records `x` as unused.

A9. Test-mode steps follow EXT firmware with 7 L and 7 C. `L_mult` is 4, so the mask counts from 0 through 127. `RelayC` bit 7 set means order LC. Default order is LC. Banks and counts are `INDUCTOR_COUNT` and `CAPACITOR_COUNT` in `remote/config.py`.

A10. Fallback mode and the serial UART must not be wired at the same time. Both want RB1 and RB2. `ATU_MODE` is `serial` or `fallback`. Fallback has no power sample, so the interlock stays inactive. TST, TUP, TDN, TSC, and TSL return Data Not Available in fallback.

A11. Fallback press widths, taken from v3.2 `button_proc`: a Tune press still held after 250 ms is tune, a press released before that is reset. Use `TUNE_LONG_MS` 400 and `TUNE_SHORT_MS` 100. Auto and Bypass are toggles after the 50 ms debounce. Use `BUTTON_TOGGLE_MS` 80. Power-up default is manual and not bypass. The remote remembers the last fallback state and presses only when the requested state differs.

A12. Choice: a one-line firmware fork, not display-side reconstruction. In ukoda `show_pwr`, when test mode is off, EEPROM cell 0x33 is on, and internal power is at least 10 (1.0 W), the reported power becomes antenna power. `send_state` then sends that value as `Power`. Forward watts are not in the stock object. Efficiency is capped at 99 after the multiply, so `Power` times 100 divided by efficiency is the wrong way back to forward watts, and it is the wrong direction for the hot-switch check. The fork adds `Forward` from the internal forward reading in `send_state`, marked `// REMOTE LINK`. Parser rules: `Forward` is forward watts. `Power` is antenna watts when efficiency is present, and forward watts only when that field is absent. Antenna watts are not forward watts times efficiency. Show the efficiency screen when forward watts are at least 1.0, efficiency was present, and antenna watts were present. Otherwise show L and C. The percent text is capped at 99. The antenna line stays the `Power` value. The SND payload is 15 bytes. The last uint16 is antenna watts times 10, so the master can show that `Power` value without multiplying forward watts by efficiency. `0xFFFF` in that field means the sample is absent, including when the efficiency flag is set. A real 0.0 W is packed as 0. Where to change the fork text: `atu100_firmware/README.md`. Where to change the screen rule: `common/display.py`. Where to change the payload: `common/protocol.py` and `docs/PROTOCOL.md`.

A13. Display strings follow the PRD examples, including one decimal on power above 10 W. The stock OLED text `PWR=0.0W` is not what we show.

A14. Line order follows the stock SW flag. JSON `Order` `LC` puts L on line 3 and C on line 4. `CL` swaps those lines. Bypass marker wins over the Auto marker because the stock code writes the dot only when Auto is on and bypass is off.

A15. Shared Pico GPIOs are identical and listed in `docs/WIRING.md`. The MCP23017 bit maps differ because the boards do not have the same buttons. Decision 8 applies to the Pico header, not to every expander bit.

A16. Master Antenna Select cycles AT1, AT2, AT3, AT4, then back to AT1. It does not select AT0. AT0 is the menu item All off.

A17. Error LED stays on until the next successful ACK, or until link loss clears for Communication Lost. RF Present LED is on when the last fresh forward power is greater than `HOT_SWITCH_WATTS`.

A18. Device boot runs `/main.py`. Flash copies `master/main.py` or `remote/main.py` to `/main.py` and copies the package directory too. Imports inside the repo stay `master.config` and `remote.config`. There is no second copy of `main.py` at the repo root.

A19. MicroPython firmware is v1.29.0 (2026-08-24) for `RPI_PICO2_W`.

A20. A scheduler exception other than `RelayFault` is a local error. The loop continues and the antenna is left as it is.

A21. `LinkState` stores the relay coil mask, the LED bit mask, the last button mask, and `order` (`LC` or `CL`). `order` is stored from the JSON `Order` field. It is not derived later. The other tuner readings are the ones listed with commit. Two I/O groups stay out of the table. The SSD1306 framebuffer is derived by `publish` in `common/display.py` from `LinkState`, so a rollback re-renders instead of storing pixels. Optocoupler coils are pulses owned by `remote/button_emulation.py`, not levels to restore. A restored pulse would press Tune, Auto, or Bypass again. After `RelayFault`, do not write a previous nonzero `relay_mask` back to the latch. `safe_off` leaves the mask at 0. The previous snapshot stays for the log. Boot starts from a fresh `LinkState` and does not write a previous mask.

## Layout notes

`common/hal.py` is the only module that imports `machine`, and that import is inside `try/except ImportError` because the host has no `machine` module. `pytest.ini` is a host tool file. `atu100_firmware/` holds the README and the unified diff. It does not vendor the rest of the ukoda tree.
