# A1 II (ILCE-1M2) 4.00: port notes

How the open gate of the A7 IV / A7S III / FX3 kits was built for the A1 II, what was checked and how, and what is not known. Everything here
is static reading of the 4.00 update or emulation of its own code; **nothing has run on an A1 II**. The working notes with every detail are
in the project's map (`a7iv_map/modding/A1M2_PORT.md`, `A1M2_PORT_ENCODER.md`, `A1M2_PORT_SCREEN.md`, `A1M2_PORT_DMM_SIZE.md`).

## The firmware

- `BODYDATA.DAT` 4.00 (model code 0x40030023) decrypts with the public CXD90057 key, like the A7 IV's. Same file set: `cpapp-b.bin`
  (image processor, Thumb, loads at 0x108000), `av-cam.bin`, `libmpr.so`, `appFw.so`, `libsencore.so`, `libJiritsu.so`.
- **Service route:** `libsencore.so` holds the A7 IV's three service-login keys (0x59f58 / 0x5a158 / 0x5a358) and `libJiritsu.so` the same
  file-write-and-load command (`adj_cmd_set_file2`, `dlopen`, `/tmp/jiritsu`). So the kit's USB route is the A7 IV's (not the A7 V's).
- av-cam.bin at physical 0x401000000 (`kemco.txt` `memrsv=0x01000000@0x401000000:ex`), as the A7 IV.
- `DeviceInfo.xml` is byte-identical to the A7 IV's and the A1's: the known-answer read cannot tell the bodies apart. The check compares four
  pages of image-processor code that differ from every other body on disk (0x128000, 0x279000, 0x501000, 0xa0d000), and every write step
  refuses unless every byte it changes holds the A1 II 4.00 stock value.

## Sensor side (`ogsq_a1m2_v1`; alternative `ogh2880_a1m2_v1`)

The A1 II's sensor is the A1's (the register matrices of the two bodies are identical). Its drive-parameter object has 44 drive modes.

| What | A1 II 4.00 |
|---|---|
| mode ids | 0xe9eb40 (44) |
| constructor caller / constructor / base constructor | 0xa0d5ec / 0xa0f442 / 0xa10246 |
| calculator (vtable slot 3) | 0x132320 |
| sensor object, drive-parameter pointer | 0x1790350 (getter 0xa0b200), control +0x6cc |
| stored records | 0x170 bytes each, base 0x24dba14 in emulation (the write step follows the pointer chain) |
| register matrix / column map | 0x11ee600 (100 rows of 32 bytes: shadow pointer + 28 columns) / 0x11ef2a0 |
| per-mode tables | crop 0xe9ebf0 (20 B rows), stream-0 window 0xfa02aa (38), stream-1 (phase detect) 0xfa09ca (38), LC 0xfa10ea (14), read-out 0xea0808 (44), geometry 0xe4b640 (12-byte rows by mode id) |
| record selector | 0x279f20: 0x820/0x8c0 -> 0xdf6844 / 0xdf73fc; 0x2820/0x28c0 -> 0xe023c4 / 0xe02f7c |

- **What full-frame 4K reads:** modes 0x820, 0x2820, 0x8c0, 0x28c0 (29.97p / 23.98p at 60 Hz, all 25.00p at 50 Hz) use matrix column 2
  (sensor mode 0x14, 2 × 2 binning), which no other mode uses: 4320 × 2430 of the 8640 × 5760 sensor, the first scaler 1:1, the second scaler
  makes 3840 × 2160.
- **The window is two register cells.** In all 25 columns in use, shadow +0x20 (start block s) and +0x24 (half-height n, × 2 in the 3 × 3
  and 6 × 6 settings) satisfy s + n = 31; full height is s = 1, n = 30 (the still modes), the 4K band s = 6, n = 25. In the three columns of
  sensor mode 0x14 the register at shadow +0x90 is 33 + n (58 / 56 / 50 at n = 25 / 23 / 17), mirrored in the read-out table's field [11].
  The design sets column 2's three cells (0x11ee706 6 -> 1, 0x11ee726 25 -> 30, 0x11ee846 58 -> 63): the 4K setting's own binning and line
  timing at full height, 4320 × 2880. About 2,912 sensor lines per frame against 6,320 / 5,056 / 5,888 at 23.98 / 29.97 / 25p.
- **Table cells** (the full-height values are those of the still and live-view modes that read the full height): crop band row 222 -> 0 and
  first phase-detect block 5 -> 0; stream-0 height 2430 -> 2880 (margins 12, 2, 8 / 8, 2 kept); stream-1 phase-detect rows 114 -> 134 (the
  count of every full-height mode; field [15] stays 36); LC [4] 535 -> 91 (= 91 + 2 × band row in 2 × 2) and [6] 631 -> 151; read-out [11]
  58 -> 63 and length 679 -> 792 (rows / 4 + 63.5, as stock); geometry band row 222 -> 0.
- **Picture records:** a row model fitted on the A1 II's own 2 × 2-binned pairs (4K, the 3840 crop, two S35 FHD pairs): 134 / 135 fields per
  side follow the stage rows, the phase-detect rows, the window row, the active rows or the band row; the A7 IV's own fitted row fields are all
  among them. Column geometry and every register word come from the firmware's split planner and packers (they rebuild every stock A1 II 4K,
  crop and S35 pair byte for byte). Self-test: four cross-rebuilds of stock pairs from one another, 0 differing fields. Design: first stage
  4332 × 2896 (crop 4320 × 2880), Lrc step 4855/4096 into the stock 4320 × 2430 front end, row pad 8 -> 6 (the firmware's fit), 203 fields
  per record; stored records +6/+7 2/1 -> 27/16 (over +4/+5 = 2/1: 27/32), 29 bytes per record, NTSC and PAL variants.
- **Real rows (`ogh2880_a1m2_v1`, R5/R6):** the same cells and window; the first scaler keeps all rows (4320 × 2880 front end), the stored
  records keep 2/1, the second scaler makes 3840 × 2560 at 1.125 on both axes. 209 fields per record.

## Output size and memory (`outsz2560_a1m2_v1`)

- Movie size table 0x1938488 (set-up 0x501834, reader 0x5214fe case 3 loads base + 0xcc): word 0x19384d0 `000f7008` -> `000f000a`
  (3840 × 2560), guards 0x19384c8 / 0x19384d4. Output buffer id 0x2d9 (11 units of 13,271,040 bytes) holds 3840 × 2560 at format code 2.
- **No raw-write-buffer step:** id 0x43e / key 0x57f has seven units of 21,410,048 bytes, about 4,800 rows of the 4K line; the stage needs
  2,896. Raw port check 0x26b9a0.

## Encoder side (`ogfile2560_hs_s_a1m2_v2`, `_v1`, `ogfilesi2560_a1m2_v1`)

- Tables: libmpr comb table 0x2d2ca8; av-cam unit-type table 0x3ab234, 686 descriptors at 0x3ab2d4, profiles 0x3c34b4 / 0x3da8b4, clip table
  0x3a9158 (codes 3 / 23); MP4 heights 0x224154 (AVC) / 0x2241a0 (HEVC) (the A7 IV's writer moved by +0x15c4); `m_vpcSt` 0x2e8a50.
- L19: 29 long-GOP descriptors (12 HEVC, 17 AVC) with their profiles, 4 comb rows, clip row, unit row, + the two MP4 heights (code sites,
  guarded by their neighbouring instructions). N19 = without the heights. I19: 4 S-I descriptors, 12 profiles, comb row 9.
- **Unit row 3 := row 2 stays** (as on the A7 IV): the A1 II's 8K class has memory, but its frame-buffer id is 0 and its ES block is the
  alternative of the 4K frame buffer in one 304.7 MB block. So **8K cannot record while applied**.
- av-cam functions are another compile than the A7 IV's (matcher 0x234acc, memory 0x22c9e8, clip 0x1a4134, start block 0x2307fc); the codec
  firmware is byte-identical to the A7 IV's.
- Checked: `emu_mp4_meta.py --build a1m2_400` (416 accepted 4K requests: tkhd / stsd / PROF say 3840 × 2560, stock profile ids, square
  pixels); `run_ogfile_emu_a1m2.py` 28 checks incl. the S-I step on top of L19.
- **Playback** is expected to work (decode set-up 0x227548 opens the 8K channel 0x47c / 0x47e unless the clip type is 14, as the A7 IV), not
  traced end to end.

## Rear screen and C3 (`lcdfill_a1m2_v1`, `lcdcycle_a1m2_v1`)

- Rear panel: 2,095,104 dots = 1024 × 682 × 3: 3:2 expected (type byte 0x1a1c638, 3; viewfinder 0x1a1c768, 4:3, not changed).
- S16: VDF fit word 0x1faca4 3 -> 0 (fit function 0x1fac50, the A7 IV's byte for byte), and the three frame tables' 3:2-panel 16:9 entries
  (0xf82404, 0xf8247c, 0xf824f4) (0, 38, 640, 404) -> (0, 0, 640, 480). 7 words, 11 guards. 11 emulated cases incl. the A1 II's own frame check.
- C19: raw C3 event 0x2150006 hooked in `process_input_event` 0x1d22164 (movie mode only, the event swallowed); the routine (1,676 bytes) in
  the zero tail of appFw's first segment, 0x4d0d8b0-0x4d0df3c (segment file size 0x4d0d8a5, mapping 0x4d0e000); calls dlsym (.plt
  0x155fe80) -> libsencore `dmm_alloc` / `sen_dma_transfer` / `dmm_free`, the system-mode accessor 0x268eb3c (+0xd508) and the layout wrapper
  0x317926c. Each press writes the fit word, the letterbox constants 0x1fafa4 / 0x1fafa8 and the three frame entries. 77 emulated cases.
- The A1 II's own De-Squeeze Display uses another calculator (0x1fae78): keep it Off.

## The kit

| Step | Library | SHA-256 |
|---|---|---|
| check (`a1m2read_v1`) | libJit_a1m2_check.so | cc4bbcac0df1a71be64840b43d6a45895791be8147bba7f6bed1246ecd2895a1 |
| dump | libJit_a1m2_dump.so | bef84fc975cf7775b51167634857f26bb61de46bfe791185f80e91e1eb8b4e83 |
| L5 / L6 (ogsq_a1m2_v1) | libJit_a1m2_L5.so / L6 | 0b3357a397e29eb193e7c50de522fbbbef393884a11b542bbd3ea463b28d6167 / 7188f400be220b4a2c7cf60221cc4a6027e4db820bb397e577ca3886b7d82279 |
| R5 / R6 (ogh2880_a1m2_v1) | libJit_a1m2_R5.so / R6 | fcb27cdbf129fb4f1f411f3dfee03b322c8751748d1b11354671e6630ee82ae6 / 933e176ac348e76b6f4d2553c9590e67fc24d5e674d4339f8d159b1083ab6c24 |
| L16 / L17 (outsz2560_a1m2_v1) | libJit_a1m2_L16.so / L17 | 2f09b46b607794fae3479d9bef9f8aad228546012ab145a859025f3a74acbfba / 2f5516ddd577bcc679120a4fef68fe3acc6ff3c292ab28daa238c9c031b56ab4 |
| L19 / L20 (ogfile2560_hs_s_a1m2_v2) | libJit_a1m2_L19.so / L20 | 88c96675d996b9c1c4ef54dcbf94bde59e2fc05a848bf6f5f05630ca33eb4d2e / 93c9a6427b098883c79b9e8b19bf4beb6603f6e56fcb70e603db8d084f9f500b |
| N19 (ogfile2560_hs_s_a1m2_v1) | libJit_a1m2_N19.so | 3e6304d5ca9bd42ed6a9e1f14bce71f0dcba0a7d2b03d8db29bd0edfab1669fa |
| I19 / I20 (ogfilesi2560_a1m2_v1) | libJit_a1m2_I19.so / I20 | bf3d88bc8bc621007bd51d13d208b8a9350f64e5b91187d00ea4971101c77018 / 0390c9179ce8daa7c273c91bba187118118a3500eec25eac02d8528f2e213d83 |
| S16 / S17 (lcdfill_a1m2_v1) | libJit_a1m2_S16.so / S17 | a4d4c8011c30f06f433b11e2011c1b40d0430f9e13a383fb6272719991a5587d / 3849213c9560131ec523c26f4d55e1c7ab48d094a6687f4039097eaf5fe7b070 |
| C19 / C20 (lcdcycle_a1m2_v1) | libJit_a1m2_C19.so / C20 | a42eef38bdea70763faeac4c1d9a5c207fe5eacbe87c3719cbdef83644dda0eb / c3167a72f599033619ca3171c8d77822632934833e158c1d1f78d2e1f7a78c38 |

- The write libraries are the A7 IV helper's code (`helper/readcheck.c`, unchanged) built with the A1 II's headers (`helper_a1m2/gen_a1m2_write.py`)
  and constants (`build_a1m2_write.sh`): IMAGER 0x1790350, CTRL_DRVPARAM 0x6cc, REC 0x170, MULTI_REC with four stored records in NTSC and PAL
  variants; av-cam at 0x401000000; the C step with MP_LIB appFw.so. The read-only helper `a1m2read.c` is the FX30 kit's with one addition:
  the four 3,000-byte picture records carry their target as a list of changed bytes, so the library fits one upload packet.
- **Checks that pass:** `emu_a1m2_write.py` 106 cases (every step: apply, again, put back, NTSC and PAL, a mixed-variant camera, lost writes,
  foreign bytes, null pointers, a missing mode id, guards, L5 and R5 against each other's state, the C routine's order and a short mapping,
  the S-I step with and without L19; and the FX30, FX3, FX2, A7C II, A7 IV and A7S III kits' libraries of the same steps write nothing on an
  A1 II). `emu_a1m2.py` 24 cases + 5 foreign kits (stock NTSC/PAL, applied, no screen, no meta, real rows; the A1, FX30, FX2 and A7 IV say
  NOT READY). `a1m2_run.py <step> --selftest` for all 17 libraries (check and dump with the emulated helper, including the dump decoder);
  `a1m2_apply.py --dry-run` for every launcher, from the published tree; the app harness (16 checks on the APK's payload).
- Android: `android/A1II-OpenGate.apk` 0.1 (com.a1m2.opengate), SHA-256 67ef6b9e17cd38f5ab8043b189aaa5fbf0f9b087222a94ddc731ca28cd64019a.

## Not known until an A1 II runs it

- Whether sensor mode 0x14 reads 2,880 rows with s = 1, n = 30 (the rule holds in every stock column, but no stock column is 2 × 2 at full
  height), and the margin rows it gives there; register +0x90 = 63.
- The squeeze lever: the A1 II's resize calculation was not emulated.
- The phase-detect row count at full height (134 taken from the full-height modes).
- That the camera computes the stored records from its 60 Hz or 50 Hz table at start-up, as the FX30 kit assumes (the step refuses otherwise).
- The 4K format code (2 on the A7 IV), panel type, that C3 sends 0x2150006, the power switch, exposure / AF / rolling shutter, heat.
- The real-rows alternative: 2,880 rows through the stages after the first scaler (the A7 IV ran 2,560 and 3,840 there).
