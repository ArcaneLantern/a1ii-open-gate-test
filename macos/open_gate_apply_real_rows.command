#!/bin/bash
# A1 II (firmware 4.00): ALTERNATIVE, try only after the default apply worked: the same state with the real-rows sensor step (the first scaler keeps all 2,880 rows).
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --real-rows "$@"
