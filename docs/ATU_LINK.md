# ATU-100 link

The remote Pico UART1 runs at 4800 baud to the ukoda serial firmware. The pinned upstream hex is `ATU-100_remote_PIC16F1938_20260412_1157.hex`. One field per outbound message. Replies are blocking, so the link is half duplex. Other commands are ignored while tuning. Local display EEPROM settings are ignored. The upstream tree is a work in progress.

Inbound objects are multiline. `json_start` sends an opening brace. Each name is indented two spaces. Fields are separated by a comma and a newline. An `Event` object is ignored. It is not data corrupted. A partial object stays buffered until the braces balance.

## Command map

| Command | Bytes |
| --- | --- |
| AM0 | `{"Auto":true}` |
| AM1 | `{"Auto":false}` |
| BYP0 | `{"Bypass":false}` |
| BYP1 | `{"Bypass":true}` |
| TUN | `{"Tune":true}` |
| STA | `{"Status":true}` |
| RST | `{"Reset":true}` |

AM0 turns Auto on and AM1 turns Auto off. That pair is reversed from Bypass and Test. `{"x":true}` is unused. The name `x` resets the PIC as soon as the closing quote arrives, so RST does not send it.

The efficiency key on the wire is `efficency`, spelled that way in the C source. `Efficency` is also accepted. `Forward` is forward watts. `Power` is antenna watts when efficiency is present.

Test mode uses `RelayI` and `RelayC`. `RelayC` bit 7 marks LC order. The L or C field stays in 0..127.

Normal reply timeout is 500 ms. Tune may stay busy for 30 s. A command is written at most 3 times.

## Fallback

Fallback mode has no forward power, so there is no hot-switch interlock, no L/C test steps, and no SWR or efficiency on the OLED. The optocouplers press Tune, Auto, and Bypass instead. Do not populate those optos and the UART at the same time.

## Firmware change

The stock hex does not send `Forward`. The one-line diff is in `atu100_firmware/README.md`. This host does not compile XC8, so the diff is documented and not built here.
