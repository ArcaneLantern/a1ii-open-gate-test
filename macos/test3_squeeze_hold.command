#!/bin/bash
# A1 II (firmware 4.00): KIT v2 TEST 3 (cold boot, SteadyShot OFF): the full state, L5, F16, L16, L19, I19, S16, C19, then one read-only session. Expected to fail like the first run until test0 and test1 are reported.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply test3 "$@"
