#!/bin/bash
# A1 II (firmware 4.00): KIT v2 TEST 1 (cold boot, SteadyShot OFF): only the sensor step L5 (full-height window, squeezed). Look at the rear screen in Movie: the whole sensor squeezed, no purple/black band, no restart? Then one read-only session.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply test1 "$@"
