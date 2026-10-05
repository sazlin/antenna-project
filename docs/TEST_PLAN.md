# Bench test plan

Start with the receiver off. Then a dummy load. The on-air section is last.

## No RF

Power both Picos with no transmitter connected. Do not require a wattmeter reading in this section. Confirm all relays off at power-up. Confirm Communication Lost clears after the poll. Select each antenna and confirm only one coil. Press F86 and confirm all coils open. Pull the RS485 plug and confirm the selected coil stays closed and both OLEDs show Communication Lost.

## Dummy load

Use low power, 5 W or less, into a dummy load before any antenna. Confirm the power text. Confirm a change above 1 W is refused. Drop power and confirm the change is allowed.

## Antennas

One band, one antenna, then the other three. One relay at a time, never two coils. A power above 1 W must be refused. Stop if the latch readback fails.
