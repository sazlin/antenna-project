# ATU-100 firmware notes

Pinned upstream hex: `ATU-100_remote_PIC16F1938_20260412_1157.hex`. Tuner baud is 4800. Do not put a hex file in this repo.

The stock `send_state` object has `Power` and `efficency`. It does not have forward watts. The host tests do not compile the PIC. This host cannot run XC8, so the diff below is documented and not compiled here.

## The one-line change

In `send_state`, add `Forward` from `g_i_Power`. Do not change the tuning algorithm.

```diff
--- a/send_state
+++ b/send_state
@@
+                // REMOTE LINK
+                json_int("Forward", g_i_Power, sft);
```

The comment `// REMOTE LINK` is on the line above `json_int("Forward", g_i_Power, sft)`.

## Build

Upstream docker image from `zsteva/mplab-pic-xc8-builder`, then `docker.sh`, then `make`. Or MPLAB X with XC8. Flash only after a backup. Read the chip first with `pk2cmd -PPIC16F1938 -GF`.
