# Summary

Host tests are the verification that ran without hardware. No Pico, no PIC programmer, and no RF were available in the host run.

The ukoda hex `ATU-100_remote_PIC16F1938_20260412_1157.hex` was not flashed here. A fork was required to add `Forward`, because the stock object sends antenna watts as `Power` and does not send forward watts. That fork was not compiled here.

These eight client decisions are open for the client to confirm:

1. Refuse an antenna change at more than 1 W forward.
2. Keep the current antenna when the RS485 link drops.
3. Use ukoda/ATU-100-remote instead of bit-bang.
4. Test mode is TST0/TST1 and the step commands, with no power cycle.
5. Master buttons include Antenna Select, plus the five menu keys, Tune, A/M, and Bypass.
6. The remote has 5 buttons and two LEDs.
7. Break-before-make is 100 ms.
8. Do not use GPIO 23, 24, 25, or 29.

What the host could not check: real relay readback, OLED pixels, RS485 on the U094, the 4800 baud tuner, and a PICkit flash of the Forward diff.
