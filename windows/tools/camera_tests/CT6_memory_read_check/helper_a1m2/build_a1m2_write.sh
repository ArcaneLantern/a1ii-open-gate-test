#!/bin/bash
# Build the A1 II 4.00 write libraries from the A7 IV helper's source (helper/readcheck.c), with this build's tables and constants
# (A1 II port, 2026-11-26). Run gen_a1m2_write.py first.
# usage: build_a1m2_write.sh        (writes libJit_a1m2_<step>.so into this folder and prints SHA-256, size, step)
# Flags are those of helper/rebuild.sh. Differences from an A7 IV build: the headers of gen_a1m2_write.py, the A1 II 4.00 libsencore.so to link
# against, and these constants (modding/A1M2_PORT.md, evidence/a1m2/helper_constants.json):
#   L5/L6, R5/R6   IMAGER 0x1790350 (the getter 0xa0b200 returns it), drive-parameter pointer at control +0x6cc (the constructor block 0xa0d682
#            stores it at 0xa0d7b2), stored record 0x170 bytes (0xa0f4ee). The headers set MULTI_REC: four stored records (0x820, 0x2820,
#            0x8c0, 0x28c0), each in an NTSC and a PAL variant. L = ogsq_a1m2_v1 (the default), R = ogh2880_a1m2_v1 (real rows, alternative).
#   L19/L20, N19, I19/I20, C19/C20   av-cam.bin at physical 0x401000000 (kemco: memrsv=0x01000000@0x401000000:ex, as the A7 IV)
# Steps: L = open gate (5/6 sensor side, 16/17 output size, 19/20 encoder side with the MP4 header heights), N19 = the encoder side without the
# heights (--no-meta; L20 puts back either), I = XAVC S-I 4K (19/20), S = the rear screen words (16/17), C = the C3 preview routine in appFw.so
# (19/20). No L13/L14: the A1 II's stock raw write buffer unit holds the 2,896-row stage (modding/A1M2_PORT_DMM_SIZE.md).
set -e
H="$(cd "$(dirname "$0")" && pwd)"
SEN="$H/../../../work/extracted/a1m2_400/0700_part_image/dev/nflasha15/lib/libsencore.so"
cd "$H/../helper"
CC=(../../../work/venv_zig/Scripts/python.exe -m ziglang cc -target aarch64-linux-gnu -std=gnu11 -O1 -Wall -Wextra -Werror -fPIC -shared -nostdlib -ffreestanding
    -fno-stack-protector -fno-builtin -fno-asynchronous-unwind-tables -Wl,-soname,libJit.so -Wl,--no-undefined -Wl,-z,now -g0 -s -Wl,-z,max-page-size=4096)
for L in 5 6; do
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogsq_a1m2_v1.h"' '-DDESIGN_LABEL="ogsq_a1m2_v1"' -DIMAGER=0x1790350UL -DCTRL_DRVPARAM=0x6ccU -DREC=0x170U \
    readcheck.c "$SEN" -o "$H/libJit_a1m2_L$L.so"
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogh2880_a1m2_v1.h"' '-DDESIGN_LABEL="ogh2880_a1m2_v1"' -DIMAGER=0x1790350UL -DCTRL_DRVPARAM=0x6ccU -DREC=0x170U \
    readcheck.c "$SEN" -o "$H/libJit_a1m2_R$L.so"
done
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz2560_a1m2_v1.h"' readcheck.c "$SEN" -o "$H/libJit_a1m2_L$L.so"
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_lcdfill_a1m2_v1.h"' readcheck.c "$SEN" -o "$H/libJit_a1m2_S$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_a1m2_v2.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_a1m2_L$L.so"
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfilesi2560_a1m2_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_a1m2_I$L.so"
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_lcdcycle_a1m2_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_a1m2_C$L.so"
done
"${CC[@]}" -DLEVEL=19 '-DMP_H="expected_mp_ogfile2560_hs_s_a1m2_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_a1m2_N19.so"
cd "$H"
for N in L5 L6 R5 R6 L16 L17 L19 L20 N19 I19 I20 S16 S17 C19 C20; do echo "$(sha256sum libJit_a1m2_$N.so | cut -d' ' -f1) $(stat -c %s libJit_a1m2_$N.so) $N"; done
