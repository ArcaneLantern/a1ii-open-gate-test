#!/bin/bash
# A1 II (firmware 4.00): put every step back to stock after test2 or test4.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply putback --real-rows "$@"
