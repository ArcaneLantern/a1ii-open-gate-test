#!/bin/bash
# A1 II (firmware 4.00): KIT v3 TEST 5 (run this FIRST, from a cold boot, SteadyShot OFF): the full-height sensor step with the stock-size picture taken from the BOTTOM of the frame. In MOVIE compare with stock (tripod) at the BOTTOM edge: A) a normal 16:9 picture framed about 9% LOWER, no band, no restart, or B) a purple/black band at the bottom and/or a restart? Then one read-only session.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply test5 "$@"
