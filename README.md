# A1 II open gate: test kit (firmware 4.00)

<p><b>Not yet run on any A1 II.</b> This kit brings the open gate that works on the A7 IV, A7S III and FX3 to the Sony A1 II (ILCE-1M2) firmware 4.00. It records a true 3840 × 2560 picture of the whole 3:2 sensor in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 23.98p (25p on a PAL camera), and makes the MP4 headers say 3840 × 2560. It also shows the whole picture at 3:2 on the rear screen, and makes the C3 button cycle an anamorphic preview: 3:2 → 2:1 → 2.25:1 → 2.4:1 → 3:2. The patch only writes to the camera's memory: a battery pull removes it.</p>

**Where it stands (2026-11-26):**

- **Built and emulated, not run.** Every step was built from the A1 II 4.00 firmware's own tables and checked against the A1 II's own code in emulation (Unicorn). Every library was run against a model A1 II (`PORT_NOTES.md`). The first A1 II owner to run it is the first test.
- **How it works on the A1 II.** In full-frame 4K the A1 II reads its sensor 2 × 2-binned, from a 16:9 band of the sensor (4320 × 2430 of the 8640 × 5760 pixels), and scales it to 4K. On this sensor the band is set by two of the sensor's own window settings, which the stills modes already use at full height. So the kit keeps the 4K mode's own sensor setting (2 × 2 binning) and line timing and only makes the window full height:

  | | Stock 4K | This kit |
  |---|---|---|
  | Sensor read-out | 4320 × 2430, 2 × 2 binned (16:9 band) | **4320 × 2880, 2 × 2 binned (the whole 3:2 sensor)** |
  | Share of the sensor (8640 × 5760) | 100% × 84% | **100% × 100%** |
  | Sensor lines read per frame | about 2,462 (of 6,320 in a 24p frame) | about 2,912 |
  | File | 3840 × 2160 | **3840 × 2560** |

  The taller picture is squeezed into the stock first-stage picture and stretched back to 3:2 at the end: the A7 IV's proven method. An alternative sensor step (`open_gate_apply_real_rows.cmd`) keeps every row through the first stage instead; try it only after the default worked.
- **The shape of the kit is the FX3/FX30 kits'**: the same launchers, the read-only check before any write, the closing read-only session, Windows, macOS and Android. Its encoder, MP4-header and XAVC S-I steps are the A7 IV's working steps at the A1 II's addresses; the screen and C3 steps are the A7 IV's too. No raw-write-buffer step is needed: the A1 II's stock buffer already holds the taller picture.

**Kits cannot be mixed up.** The FX30, FX3, FX2, ZV-E1 and A7S III kits' check libraries say NOT READY on an A1 II, and their write steps (and the A7 IV's) write nothing on one. This kit's check says NOT READY on an A1 (the first model, same sensor), FX30, FX2 or A7 IV. Every write step writes nothing unless each byte it changes holds exactly the A1 II 4.00 stock value. All of this was checked in emulation.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 4.00 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | **The debug dump for testers.** The same as the check, plus: memory map, the camera's own logs (kernel and image processor), the sensor's register state and window cells, the stored mode records (with the window they program), the scaler's pages, the display (panel type, fit word, frame tables, the C3 routine's constants) | No |
| `open_gate_apply.cmd` | Applies open gate in six steps: sensor, output size, encoder (XAVC HS and XAVC S, with the MP4 headers), XAVC S-I, rear screen at 3:2, the C3 preview routine. Ends with one read-only dump | **Yes: memory only** |
| `open_gate_apply_no_screen.cmd` | Only the four open-gate steps (no rear-screen or C3 step) | **Yes: memory only** |
| `open_gate_apply_no_meta.cmd` | Open gate with the encoder step that leaves the MP4 headers at 3840 × 2160 | **Yes: memory only** |
| `open_gate_apply_no_si.cmd` | Open gate without the XAVC S-I 4K step | **Yes: memory only** |
| `open_gate_apply_real_rows.cmd` | **Alternative, after the default worked:** the same, with the sensor step that keeps all 2,880 rows through the first stage | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts every step back (after any of the applies but the real-rows one) | Yes: memory only |
| `open_gate_putback_real_rows.cmd` | Puts every step back after `open_gate_apply_real_rows.cmd` | Yes: memory only |
| `screen_putback.cmd` | Puts the screen and C3 steps back | Yes: memory only |

Nothing in this kit writes to the camera's firmware or to its settings.

## Before you start

1. The camera's menu must show **Ver. 4.00**. On any other version, stop and tell us the version.
2. **USB Connection Mode: Mass Storage (MSC).**
3. A charged battery. Do not record or play back while a step runs.
4. **Modes.** Below, "STILL" means the Still/Movie/S&Q switch under the mode dial on **Still**, with the mode dial on P, A, S or M; "MOVIE" means the switch on **Movie**.

## Windows, once

1. Install Python 3.10 or later from python.org (with the "py launcher").
2. Run `windows/setup.cmd`.
3. Install the libusb-win32 driver for the camera with [Zadig](https://zadig.akeo.ie): Options, List All Devices, pick the camera, choose libusb-win32, Replace Driver. The first run switches the camera to service mode, where it shows up as a new device (054C:0336 on the other bodies): install the driver for that one too, then run the step again.

## macOS, once (not run with an A1 II yet)

The macOS kit is the A7 IV kit's macOS port, carried over unchanged apart from the launcher names. It runs the same scripts as Windows (`windows/tools`).

1. Python 3.9 or later: the one macOS offers with the Xcode Command Line Tools (run `xcode-select --install` in Terminal) works, or install it from python.org.
2. Double-click `macos/setup.command`. It sets up Python and the USB library the scripts use. No Homebrew and no driver are needed.
3. Each Windows launcher has a macOS twin with the same name (`macos/check_readonly.command`, `dump_info.command`, `open_gate_apply.command`, and so on). Everything below that says `.cmd` works the same with the `.command` file.

Each live run asks for your Mac password: macOS keeps its own driver on the camera's USB connection, and only an administrator can hand the camera over to the script. The script unmounts the camera's memory card first; it does not erase anything on it. The results go to the same `windows/camera_private` folder.

If macOS refuses to open a .command file ("unidentified developer" or "could not verify"), open System Settings > Privacy & Security, scroll down and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the .command file into the window, and press Return.

## Android (not run on a phone or camera yet)

`android/A1II-OpenGate.apk` runs this kit from a phone connected to the camera by USB-C (or an OTG adapter). It carries exactly the files in `windows/tools` of this commit and runs them unchanged; only the USB access, the dialogs and the folder for the results are the phone's.

1. Install the APK (allow installing from unknown sources). It installs beside the other kits' apps; they do not share anything on the phone.
2. Set the camera as for the PC (below), and also **USB Power Supply: Off**, or it charges from the phone.
3. **1. Read-only check** first: the apply starts only after a check on this phone said READY. Then **2. Apply to camera**. The boxes choose: "Screen steps" (the rear screen and C3 steps), "XAVC S-I 4K step", and "Real-rows sensor step" (the alternative; leave it unticked at first). **Dump info** is the debug dump.
4. When Android asks to open *A1 II Open Gate* for the camera, tick **Always** and press OK. It comes up twice: once in Mass Storage, once in service mode.
5. When the log says **unplug and plug in again**, do that with the phone cable. Never switch the camera off.
6. **Stop waiting** ends a wait for the camera. It never interrupts a step that is talking to the camera.
7. Afterwards, **Export logs** writes a zip to `Download/A1II-OpenGate/` on the phone: send that zip back.

**Self-test** and **Dry run** need no camera and send nothing.

## The read-only steps (check and debug dump)

Each launcher asks for the firmware version the menu shows. Each run makes a new folder in `windows/camera_private`: the report (`a1m2_report.txt`), the raw result, and for a dump the coprocessor pages it copied (`cp_*.bin`).

- **Check or dump in the stills state:** set STILL, connect, run the launcher.
- **Dump of the 4K state:** set File Format XAVC S 4K (or XAVC HS 4K) at 24p, S&Q off. Set MOVIE, record a few seconds, stop. **Stay in MOVIE**, connect, run `dump_info.cmd`.

What they do to the camera: they switch it to service mode, write one small program file to the service partition, which the camera loads once, and delete that file again in the same session. The program only reads and creates one file, its report, on the camera's RAM disk. Its source is `windows/tools/camera_tests/CT6_memory_read_check/helper_a1m2/a1m2read.c`.

## The write steps

**What they change.** Six groups of bytes in the running camera's memory, one per step:

1. **Sensor** (`ogsq_a1m2_v1`): in the four full-frame 4K drive modes (24p/25p and 30p, each in two variants that share the sensor setting), the sensor window full height instead of the 16:9 band:
   - three cells of the sensor's register table for the 4K setting (window start block 6 → 1, half-height 25 → 30, and a companion register 58 → 63);
   - the per-mode tables (window height 2430 → 2880, the band's offset 222 → 0, the phase-detect rows it carries 114 → 134, the read-out length 679 → 792);
   - the four 4K picture records (first stage 4332 × 2896, squeezed into the stock 4320 × 2430 picture);
   - 29 bytes of each mode's stored record, with the vertical ratio 27/32 that makes the scaler keep every row. The camera computes those records at start-up from its NTSC or PAL table; the step finds which and writes the matching values.
2. **Output size** (one word): 3840 × 2160 becomes 3840 × 2560.
3. **Encoder** (101 + 6 sites): the encoder's tables for XAVC HS 4K and XAVC S 4K at 23.98p and 25p, and the two height values the MP4 writer puts in the file's headers, 2160 → 2560. `open_gate_apply_no_meta.cmd` leaves the headers at 2160.
4. **XAVC S-I 4K** (16 + 1 sites): the same for the four XAVC S-I 4K settings at 23.98p and 25p. `open_gate_apply_no_si.cmd` leaves it out.
5. **Screen** (7 words): a 16:9 live view fills the 3:2 rear screen (it holds the whole 3:2 picture squeezed, so it is shown at its true shape), and the focus and tracking frames are told where the picture now is.
6. **C3 preview** (code in the camera's application, `appFw.so`: a small routine in unused space at the end of its program, then one branch to it): in MOVIE, each press of **C3** steps the rear screen through 3:2 → 2:1 (for 1.33x anamorphic lenses) → 2.25:1 (1.5x) → 2.4:1 (1.6x) → 3:2, squeezed with black bars, not cropped. It changes only the preview, not the file.

Each step first checks that every byte it is about to change holds its stock value, writes, reads back, and undoes its own writes if anything does not match. `open_gate_apply_no_screen.cmd` runs only the first four.

**What we do not know yet.** Everything on an A1 II. The points that worry us most:

- **The full-height window in the 4K sensor setting.** No stock A1 II movie mode reads the full height 2 × 2-binned; the full height is read by the stills modes (at full resolution or 3 × 3 binning). The window settings follow a rule every one of the 25 sensor settings in use obeys (start + half-height = 31; full height = 1 and 30), and the companion register follows its own rule in the three 4K-class settings, but the sensor has never been asked for this combination. If it refuses, expect a broken picture, black rows, or a restart when MOVIE starts, not lasting harm: a battery pull clears it.
- **The margins at full height.** The kit keeps the 4K band's margin rows (8 above and below the picture). The sensor may give fewer at full height: then the bottom few rows may be dark or repeated. The dump shows it.
- **The phase-detect rows** (autofocus). The window carries 134 rows of phase-detect data instead of 114 (the count every full-height mode uses). If it is wrong, autofocus may misbehave or the picture may break.
- **The squeeze lever.** The A1 II's resize calculation was not emulated (the A7 IV's was); if the 27/32 ratio does not act, expect the middle 16:9 of the tall picture, not a crash.
- **The power switch.** On the A7 IV switching off and on keeps the patch; on the A7S III it removes it. Not known on the A1 II: keep it switched on during the apply.
- **The rear panel** is expected to be 3:2 (2,095,104 dots = 1024 × 682 × 3). The closing dump reads its type.
- **Exposure, autofocus, rolling shutter, long recordings, heat:** the sensor reads about 18% more rows per frame, so rolling shutter grows by about the same.

**While it is applied**

- Use only **XAVC HS 4K, XAVC S 4K or XAVC S-I 4K at 24p (23.98p), or 25p on a PAL camera.** 29.97p/30p reads the tall window too and shares the picture records, but its encoder is not set up: do not record it. 60p, 120p, S&Q, HD formats, the Super 35 / APS-C crop and Proxy Recording are not set up and are likely to fail.
- **8K cannot record** while it is applied (the encoder step gives the 8K class the 4K memory). A battery pull restores 8K.
- Keep the A1 II's own **De-Squeeze Display Off**: while it is on, the camera uses its own ratio and the C3 states do not act. While the kit is applied, C3 does not run the function assigned to it in MOVIE.
- On the rear screen every 16:9 picture fills the 3:2 screen, so other movie formats look stretched there. The viewfinder is not changed (it keeps the squeezed 16:9 preview). HDMI output is not part of this kit and has not been checked.
- **Playback on the camera** of the 3840 × 2560 clips is expected to work (the A1 II opens playback with the same 8K channel the A7 IV plays these clips with), but it was not traced end to end. Try ONE clip; if the camera says it cannot display it, do not retry, and check the clips on a computer.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K or XAVC S-I 4K) and 24p. S&Q off. De-Squeeze Display Off. Proxy Recording Off. APS-C/Super 35 Off.
2. Set STILL. Then pull the battery for 10 seconds and switch on, so that nothing of an earlier run is left. Do not go to MOVIE yet.
3. Connect USB and run `windows/check_readonly.cmd`. It must say VERDICT READY.
4. Run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
5. It runs six steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until the script says it is finished.
6. After the six steps the script asks for one more session, which only reads. **Unplug USB, set MOVIE, look at the screen for five seconds, press C3 a few times, and plug in again.** The script then runs the debug dump by itself and prints the window the 4K mode now programs, the sensor's window cells and the rear panel's type.
7. When it says so, unplug. The rear screen should show the whole picture at 3:2.
8. Record 20 to 30 seconds and stop. Check the clip on a computer. Then try XAVC S and XAVC S-I.
9. To return to stock: battery out for 10 seconds, or `open_gate_putback.cmd`.

**If the camera restarts by itself** at any point: do not pull the battery. Set STILL, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds. The image processor keeps its own log across a restart without power loss, and the dump reads it.

**Please send back**

- The zipped `windows/camera_private` folder, with the closing dump of the apply in it.
- What the rear screen showed in MOVIE before recording: the whole 3:2 picture, or lines, wrong colours, black or repeated rows at the top or bottom, flicker. And each C3 state.
- The clip, or its properties: size, frame rate, codec, for each of XAVC HS, XAVC S and XAVC S-I.
  - **Field of view:** a still photo of the same scene from a tripod, so we can see how much of the sensor height the clip has (expected: the whole photo).
  - **MediaInfo:** `mediainfo --Output="Video;%Width%x%Height% original %Width_Original%x%Height_Original%" FILE` should give 3840x2560 with no "original" size. ffprobe cannot show the header change: it reads the size from the stream.
  - **Editors:** whether Resolve or Premiere opens the original file at 3:2.
- Autofocus: does it find and hold focus on a subject near the top or bottom of the 3:2 frame? Do the focus and tracking frames sit on the subject?
- **One check after a power-off.** When you are done: switch the camera off and on with the power switch (no battery pull), set STILL, run `windows/check_readonly.cmd`, and include that folder. It tells us whether the power switch removes the patch on the A1 II.
- Your settings: file format and record setting, frame rate, NTSC or PAL, picture profile / Log, SteadyShot.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Set STILL, connect USB, run `dump_info.cmd`, and send the folder. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery. `open_gate_apply_no_screen.cmd` applies open gate without the screen and C3 steps; `open_gate_apply_no_si.cmd` without the S-I step.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

**To remove only the screen and C3 steps:** set STILL and run `windows/screen_putback.cmd`.

**The real-rows alternative** (`open_gate_apply_real_rows.cmd`, only after the default worked): the same apply with a sensor step whose first stage keeps all 2,880 rows (the A7 IV ran this form after its squeezed one worked, and it gave more vertical detail). Put it back with `open_gate_putback_real_rows.cmd` or a battery pull. After it, the read-only check counts the four picture records as OTHER and says NOT READY: that is expected.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 4.00 update*: another firmware or model. Nothing further is sent.
- *DIFFERS from the 4.00 update* in a check: not an A1 II on 4.00 (an A1, FX30, FX2 or A7 IV gives this too). The apply will not start.
- *the stored records hold neither timing variant*: the camera's mode records are not what the 4.00 software computes. Nothing was written; send the folder.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug, and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/`:
  - the scripts, the pinned program files and their source;
  - the patch designs of every step;
  - the builders and emulations of the designs (`tools/modding/a1m2`).
- `macos/`: `setup.command` and one `.command` launcher per Windows launcher; they run `windows/tools`.
- `android/A1II-OpenGate.apk`: the phone app, carrying `windows/tools` as published here.
- `PORT_NOTES.md`: how the open gate was built for the A1 II, what was checked and how, the address map, and what is not known.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
