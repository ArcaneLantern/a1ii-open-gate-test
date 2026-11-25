#!/bin/bash
# A1 II (firmware 4.00): apply the open-gate state: a 3840x2560 file of the whole 3:2 sensor (4320x2880, 2x2 binned) in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K (24p, 25p on PAL), MP4 headers at 3840x2560, the rear screen at 3:2 and the C3 de-squeeze preview cycle (six steps, then one read-only session). NOT YET RUN ON AN A1 II.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply "$@"
