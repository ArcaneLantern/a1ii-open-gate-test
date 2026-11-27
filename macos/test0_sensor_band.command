#!/bin/bash
# A1 II (firmware 4.00): KIT v2 TEST 0 (diagnostic; run 2 showed it moves the read-out, run test5 first now; cold boot, SteadyShot OFF): only the sensor's window registers at full height, everything else stock. Then one read-only session.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply test0 "$@"
