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
| check (`a1m2read_v2`, kit v2) | libJit_a1m2_check.so | 822d24f542e0479fc03aa0f5f16066e9d194cd5b72a169a7a2a39aa2a2de0aee |
| dump (`a1m2read_v2`: + the resize view and margin pages) | libJit_a1m2_dump.so | e9d50ac50158ad35ea43fdd64da3a6b9fc912bda90724bdb56889b014e5e5718 |
| L5 / L6 (ogsq_a1m2_v1) | libJit_a1m2_L5.so / L6 | 0b3357a397e29eb193e7c50de522fbbbef393884a11b542bbd3ea463b28d6167 / 7188f400be220b4a2c7cf60221cc4a6027e4db820bb397e577ca3886b7d82279 |
| R5 / R6 (ogh2880_a1m2_v1) | libJit_a1m2_R5.so / R6 | fcb27cdbf129fb4f1f411f3dfee03b322c8751748d1b11354671e6630ee82ae6 / 933e176ac348e76b6f4d2553c9590e67fc24d5e674d4339f8d159b1083ab6c24 |
| L16 / L17 (outsz2560_a1m2_v1) | libJit_a1m2_L16.so / L17 | 2f09b46b607794fae3479d9bef9f8aad228546012ab145a859025f3a74acbfba / 2f5516ddd577bcc679120a4fef68fe3acc6ff3c292ab28daa238c9c031b56ab4 |
| B5 / B6 (fhband_a1m2_v1, kit v2 test0) | libJit_a1m2_B5.so / B6 | f4b7f029629a5d380d3b2390090aef4daace205b20f8e7a96a36edac22cbe7c8 / 6b42f041650008699bce5b17ef5a829485e22746c1d4031f6f1156418a4f4fa6 |
| F16 / F17 (fehold_a1m2_v1, kit v2) | libJit_a1m2_F16.so / F17 | bd38f3d9ef71ff426f2e9c85394613cba7b77cca8f0483b8450a0bb0cc018d90 / 2d3c1ef67737264768947e3791d40106a466f5fd3b898ad8ed1e5c442abe9211 |
| L19 / L20 (ogfile2560_hs_s_a1m2_v2) | libJit_a1m2_L19.so / L20 | 88c96675d996b9c1c4ef54dcbf94bde59e2fc05a848bf6f5f05630ca33eb4d2e / 93c9a6427b098883c79b9e8b19bf4beb6603f6e56fcb70e603db8d084f9f500b |
| N19 (ogfile2560_hs_s_a1m2_v1) | libJit_a1m2_N19.so | 3e6304d5ca9bd42ed6a9e1f14bce71f0dcba0a7d2b03d8db29bd0edfab1669fa |
| I19 / I20 (ogfilesi2560_a1m2_v1) | libJit_a1m2_I19.so / I20 | bf3d88bc8bc621007bd51d13d208b8a9350f64e5b91187d00ea4971101c77018 / 0390c9179ce8daa7c273c91bba187118118a3500eec25eac02d8528f2e213d83 |
| S16 / S17 (lcdfill_a1m2_v1) | libJit_a1m2_S16.so / S17 | a4d4c8011c30f06f433b11e2011c1b40d0430f9e13a383fb6272719991a5587d / 3849213c9560131ec523c26f4d55e1c7ab48d094a6687f4039097eaf5fe7b070 |
| C19 / C20 (lcdcycle_a1m2_v1) | libJit_a1m2_C19.so / C20 | a42eef38bdea70763faeac4c1d9a5c207fe5eacbe87c3719cbdef83644dda0eb / c3167a72f599033619ca3171c8d77822632934833e158c1d1f78d2e1f7a78c38 |

- The write libraries are the A7 IV helper's code (`helper/readcheck.c`, unchanged) built with the A1 II's headers (`helper_a1m2/gen_a1m2_write.py`)
  and constants (`build_a1m2_write.sh`): IMAGER 0x1790350, CTRL_DRVPARAM 0x6cc, REC 0x170, MULTI_REC with four stored records in NTSC and PAL
  variants; av-cam at 0x401000000; the C step with MP_LIB appFw.so. The read-only helper `a1m2read.c` is the FX30 kit's with one addition:
  the four 3,000-byte picture records carry their target as a list of changed bytes, so the library fits one upload packet.
- **Checks that pass (kit v2):** `emu_a1m2_write.py` 132 cases (v1's 106 + F16/F17 + B5/B6: NTSC and PAL, again, put back, a mixed-variant camera, lost writes, B5 against L5/R5 states and back, B6 on L5's state touching only its own sites) (every step: apply, again, put back, NTSC and PAL, a mixed-variant camera, lost writes,
  foreign bytes, null pointers, a missing mode id, guards, L5 and R5 against each other's state, the C routine's order and a short mapping,
  the S-I step with and without L19; and the FX30, FX3, FX2, A7C II, A7 IV and A7S III kits' libraries of the same steps write nothing on an
  A1 II). `emu_a1m2.py` 24 cases + 5 foreign kits (stock NTSC/PAL, applied, no screen, no meta, real rows; the A1, FX30, FX2 and A7 IV say
  NOT READY). `a1m2_run.py <step> --selftest` for all 21 libraries (check and dump with the emulated helper, including the dump decoder);
  `a1m2_apply.py --dry-run` for every launcher, from the published tree; the app harness (19 checks on the APK's payload: Test 0 to Test 4, the put-backs, the full apply refused).
- Android: `android/A1II-OpenGate.apk` 0.3 (com.a1m2.opengate; Test 0 to Test 4 and Put back Test 0 buttons), SHA-256 17d93d4870377e5dd4cc855726423faa418bcb2cf9b03e659f3bb8c81e4509ba.
- Every A1 II library rebuilds to its pin against the final shared `helper/readcheck.c` (another session's MP_LD blocks, 2026-11-26 22:40); the published tree carries the final copies of it and `ct6_level1_run.py`.

## First camera run (kit v1, 2026-11-26) and kit v2

**The run** (one tester, many applies in one evening; logs `a7iv_map/evidence/a1m2/tester_2026-11-26`): every step DONE, every site TARGET
after the apply, and the sensor's register copy in the 4K mode held start block 1, half-height 30, +0x90 63 (five closing dumps). In MOVIE the
live view showed the picture moved up with a purple/black band at the bottom; about 15 s later, or at once at record start, the camera restarted.
The image processor's kept log: CAM_VD_SEQUENCE data abort at 0x509c76 = the deliberate 'FW: S-Ele Refresh ng force exception' (counter
0x194f0dc >= 11 frames with a pipeline stage still busy; the A7 IV's F662 signature), with the resize set-up's view 0x16237b0 in r4/r6/r8.
So the lower part of each frame never arrives. Candidates:
- the sensor does not deliver 2,880 rows in mode 0x14 with s 1 / n 30 (the window registers did reach its register copy);
- the raw port: if binned 4K raw were 2 bytes per pixel (the format table at 0x26bc7c allows it), the 21,410,048-byte unit holds about 2,471
  rows of 4332 pixels, less than the 2,896-row stage (not shown: the 4K records' raw format was not traced);
- the A1 II's first-scaler override in the resize set-up (F1019 on the FX2): **ruled out in emulation.** `build/emu_rcinput_a1m2.py` runs
  0x521438 alone (the override 0xbceed4 is called at 0x521778 when view byte +5 is set; it stores output / (1 - margin), capped at the crop
  +0x38/+0x3a, only when that is WIDER than the records' first-scaler width). With ogsq_a1m2_v1 the crop is 4320 x 2880 and the records'
  first-scaler size 4320 x 2430; the capped width can never exceed 4320, so at margins 0, 0x800, 0x1000, 0x1800, 0x2000 and 0x3000 the view
  keeps 4320 x 2430, equal to what the records deliver (7/7 checks; evidence/a1m2/rcinput_emu_a1m2.json).

**Kit v2** takes the state apart: test0 = B5 only (`fhband_a1m2_v1`, run FIRST: the sensor's 3 window cells and the read-out table's [11]/[20]/[21] at
full height, the four stored records recomputed (7 bytes each, NTSC/PAL, +4..+7 unchanged), every other table and both picture-record pairs
stock: the stock 2,446-row first stage takes the first lines the sensor sends, so the framing moves up ~9% if the sensor reads full height and
stays as stock if not; put back B6 = test0_putback), test1 = L5 only, test2 = R5 only, test3 = L5, F16, L16, L19, I19, S16, C19 (= apply), test4 = R5, L16, L19,
I19, S16, C19; SteadyShot Off; after a restart, dump before any battery pull. Since the override is ruled out, the full state is expected to
fail like the first run: `a1m2_apply.py apply` refuses and points to the tests, and the open_gate_apply*.cmd launchers are withdrawn. New: F16/F17 `fehold_a1m2_v1` (word
0x521760 000f15d0 -> 000f15e0: `beq 0x521790` -> `b 0x521790`, the override never applied; guards 0x521750 / 0x521764, 16 bytes each;
`build/build_ram_words_a1m2.py --fehold`), and the read-only helper `a1m2read_v2`, whose dump adds the view page 0x1623000 and the margin
page 0x1951000 and reports the view's crop, first-scaler size and output, whether it AGREES with what the picture records deliver, the
margin words, and the F16 word.

## Not known until an A1 II runs it

- Whether sensor mode 0x14 reads 2,880 rows with s = 1, n = 30 (the rule holds in every stock column, but no stock column is 2 × 2 at full
  height), and the margin rows it gives there; register +0x90 = 63.
- The squeeze lever: the A1 II's resize calculation was not emulated.
- The phase-detect row count at full height (134 taken from the full-height modes).
- That the camera computes the stored records from its 60 Hz or 50 Hz table at start-up, as the FX30 kit assumes (the step refuses otherwise).
- The 4K format code (2 on the A7 IV), panel type, that C3 sends 0x2150006, the power switch, exposure / AF / rolling shutter, heat.
- The real-rows alternative: 2,880 rows through the stages after the first scaler (the A7 IV ran 2,560 and 3,840 there).
