# A1 II open gate: test kit v3 (firmware 4.00)

<p><b>Not working yet: this is a diagnosis kit.</b> The goal is the open gate that works on the A7 IV, A7S III and FX3, on the Sony A1 II (ILCE-1M2) firmware 4.00: a true 3840 × 2560 picture of the whole 3:2 sensor in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 23.98p (25p on a PAL camera), MP4 headers that say 3840 × 2560, the whole picture at 3:2 on the rear screen, and the C3 button cycling an anamorphic preview (3:2 → 2:1 → 2.25:1 → 2.4:1 → 3:2). Everything is written to the camera's memory only: a battery pull removes it.</p>

**Right now: run only test 5 and report.** The full open gate with the C3 preview cycle waits for test 5's answer.

## What the runs so far showed

**Run 1 (kit v1, 2026-11-26), the full state:**

- **Every step applied correctly.** Every patch site held its new bytes afterwards, and the sensor really received the full-height window (its register copy showed the new values in the 4K mode).
- **In MOVIE the live view was wrong:** the picture sat too high, with a purple/black band across the bottom of the screen.
- **The camera then restarted:** about 15 seconds after entering MOVIE, or at once when recording started (red screen).
- **The camera's own log names the restart:** its image processor stops itself on purpose ("S-Ele Refresh ng force exception") when one stage of the picture pipeline has not finished for 11 frames in a row. The A7 IV hit the same stop during its own development, each time because a stage was told to expect more picture rows than it received.
- **What it means:** the lower part of each frame never arrives. A size override in the A1 II's resize set-up (the cause of the same restart on the FX2) turned out not to be the cause: in emulation it changes nothing in this state.

**Run 2 (kit v2 test 0, 2026-11-26), the sensor's window settings alone:**

- **No restart.** The picture filled the screen.
- **The sensor moved its read-out:** it honours the full-height window setting and starts reading at another row.
- **Fine horizontal stripes about every 30 rows and a magenta cast:** expected in this test. The sensor's fixed-row corrections stay stock, so they land on the wrong rows once the read-out has moved. They are not what the tests ask about.
- Test 0 does not show the extra rows, and it does not include the rear-screen or C3 steps. Test 0 and test 5 are diagnostics only.

**The open question:** does the sensor send rows **below** the end of the stock 16:9 band, or does the frame stop after about 2,462 lines? Test 5 answers exactly that.

## Test 5 (kit v3): run this first, and only this

**SteadyShot OFF.** If you also try Active, say so in the report.

`test5_bottom_band.cmd` (put back: `test5_putback.cmd`; Android: **Test 5** button) applies **the full open-gate sensor step**: the window at full height, the read-out length, and the sensor's matrix settings. The picture records are set so that the camera takes a **normal-size 16:9 picture from the BOTTOM of the full-height frame**. Every other table stays stock.

**How to run test 5 and read the result (please do this carefully, it decides what comes next):**

1. Before the cold boot, in stock 4K 24p (MOVIE, nothing applied), put the camera on a **tripod**. Frame a scene with something recognisable right at the **BOTTOM edge** of the picture, for example a line on the floor, the edge of a table or a book on a shelf. Note exactly what is at the bottom edge, or take a phone photo of the rear screen. Do not move the camera or the zoom from now on.
2. In the menu, set File Format XAVC HS 4K (or XAVC S 4K) at 24p (25p on a PAL camera). Turn S&Q, Proxy Recording, APS-C/Super 35, De-Squeeze Display and SteadyShot Off.
3. Set STILL, then **cold boot**: pull the battery for 10 seconds and switch on. Do not go to MOVIE yet.
4. Connect USB and run `check_readonly.cmd`. It must say VERDICT READY. **Kit v3 needs a check made with kit v3**; an older one does not count.
5. Run `test5_bottom_band.cmd`. It asks for the firmware version and a typed YES. **Do not switch the camera off and do not pull the battery** until it says it has finished.
6. At the end the script asks for one more session, which only reads. Unplug USB, set MOVIE and watch the rear screen for at least 20 seconds. Compare it with what you noted, then plug in again. The script runs the debug dump itself.
7. Then unplug and try to record 10 seconds.

**What you should see:**

- **A) The sensor delivers the full height:** a normal 16:9 picture, framed about **9% LOWER** than stock. More is visible below the old bottom edge and less at the top. There is no band and no restart, and a recording works. Report "A: lower".
- **B) The frame stops early:** a **purple or black band across the bottom** (about 18% of the picture height) and/or a **restart**, as in the first run. Report "B: band" and say when the restart came (while you watched, when you pressed record, or not at all).
- Stripes or a colour cast in the picture are possible (the same fixed-row corrections as in test 0). Mention them, but they do not decide A or B.

**After test 5, report:**

- A or B, and a phone photo of the rear screen next to your stock photo;
- whether the camera restarted, and when;
- whether a recording was made, and its size (MediaInfo, see below);
- the zipped `windows/camera_private` folder (Android: **Export logs**).

**If the camera restarts by itself:** do NOT pull the battery first. Set STILL, unplug and replug USB, run `dump_info.cmd`, and only then cold boot. The kit v3 dump also copies the camera's kernel log and the image processor's own print log (the lines that name a restart, such as "S-Ele Refresh ng" or "AIF ... memsize"). Whether these logs survive a restart is not known yet, but a battery pull certainly clears them. If the camera does not respond at all, pull the battery.

**What the answers tell us:**

- **A (lower, no band, no restart):** the sensor delivers all its rows. The open gate can work on the A1 II; the next kit fixes the stage that the full state overruns.
- **B (band or restart):** only about 2,462 lines arrive from the sensor in this setting. The full-height frame cannot work this way, and another sensor setting is needed.

## The other tests (later; we will say which, after test 5)

They stay in the kit but are not needed now. Each runs from a cold boot with SteadyShot OFF, followed by one read-only dump.

| # | Launcher (Windows; macOS `.command` twins; Android: Test 0 to Test 4 buttons) | What it applies |
|---|---|---|
| 0 | `test0_sensor_band.cmd` (put back: `test0_putback.cmd`) | Only the sensor's window settings at full height. Ran in run 2: the read-out moved |
| 1 | `test1_sensor_only.cmd` | Only the sensor step L5: the full-height window, squeezed into the stock 16:9 picture |
| 2 | `test2_real_rows_only.cmd` | Only the real-rows sensor step R5: the same window, every row kept through the first stage |
| 3 | `test3_squeeze_hold.cmd` (the full state; expected to fail like the first run for now) | Sensor (squeezed), F16, output size 3840 × 2560, encoder (HS, S, MP4 headers), XAVC S-I, rear screen 3:2, C3 cycle |
| 4 | `test4_real_rows.cmd` (the full state, real rows) | The same with the real-rows sensor step |

## All launchers

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 4.00 software the port was made from, and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | **The debug dump for testers.** Everything the check reads, plus: the kernel log and the image processor's print log (kit v3), the processor's own log, the sensor's register state and window cells, the stored mode records (with the window they program), the resize set-up's view and margins, and the display | No |
| `test5_bottom_band.cmd` | **Test 5 (run this first)**, followed by one read-only dump | **Yes: memory only** |
| `test5_putback.cmd` | Puts back test 5 only (after any other test use the put-backs below or a cold boot) | Yes: memory only |
| `test0_sensor_band.cmd` … `test4_real_rows.cmd` | The other tests above, each followed by one read-only dump | **Yes: memory only** |
| `test0_putback.cmd` | Puts back test 0 only | Yes: memory only |
| `open_gate_putback.cmd` | Puts every step back (after test 1, test 3 or kit v1's apply; a step that finds stock bytes says NOTHING TO DO) | Yes: memory only |
| `open_gate_putback_real_rows.cmd` | Puts every step back after test 2 or test 4 | Yes: memory only |
| `screen_putback.cmd` | Puts back only the screen and C3 steps | Yes: memory only |

The full-apply launchers of kit v1 (`open_gate_apply*.cmd`) are withdrawn; `a1m2_apply.py apply` refuses and points to the tests.

Nothing in this kit writes to the camera's firmware or to its settings. A cold boot (battery out for 10 seconds) also undoes everything.

## Before you start

1. The camera's menu must show **Ver. 4.00**. On any other version, stop and tell us the version.
2. Set **USB Connection Mode: Mass Storage (MSC)**.
3. Use a charged battery. Do not record or play back while a step runs.
4. **Modes.** Below, "STILL" means the Still/Movie/S&Q switch under the mode dial on **Still**, with the mode dial on P, A, S or M. "MOVIE" means the switch on **Movie**.

## Windows, once

1. Install Python 3.10 or later from python.org (with the "py launcher").
2. Run `windows/setup.cmd`.
3. Install the libusb-win32 driver for the camera with [Zadig](https://zadig.akeo.ie): Options, List All Devices, pick the camera, choose libusb-win32, Replace Driver. The first run switches the camera to service mode, where it shows up as a new device: install the driver for that one too, then run the step again.

## macOS, once

1. Install Python 3.9 or later. The one macOS offers with the Xcode Command Line Tools works (run `xcode-select --install` in Terminal), or install it from python.org.
2. Double-click `macos/setup.command`.
3. Each Windows launcher has a macOS twin with the same name (`macos/test5_bottom_band.command` and so on). Each live run asks for your Mac password: it is needed to hand the camera's USB connection to the script.

If macOS refuses to open a .command file, open System Settings > Privacy & Security and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the file into the window, and press Return.

## Android

`android/A1II-OpenGate.apk` (version 0.4) runs this kit from a phone connected by USB-C. It carries exactly the files in `windows/tools` and runs them unchanged.

1. Set **USB Power Supply: Off** on the camera.
2. Press **1. Read-only check** first.
3. Then press **Test 5** (**Put back Test 5** undoes it). Tests 0 to 4 are for later. The **Full apply** button only says that the kit uses the tests.
4. When the log says unplug and plug in again, do that with the phone cable. Never switch the camera off.
5. After a restart, press **Dump info** before you pull the battery.
6. **Export logs** writes a zip to `Download/A1II-OpenGate/`: send it back.

## Checking a clip

- **MediaInfo:** `mediainfo --Output="Video;%Width%x%Height% original %Width_Original%x%Height_Original%" FILE` gives 3840x2160 after test 5, 0, 1 or 2, and should give 3840x2560 with no "original" size after test 3 or test 4. ffprobe cannot show the header change: it reads the size from the stream.
- **Field of view:** take a still photo of the same scene from a tripod. It shows how much of the sensor height the clip covers.

## While a full state is applied (test 3 or 4)

- Use only **XAVC HS 4K, XAVC S 4K or XAVC S-I 4K at 24p (23.98p), or 25p on PAL.** 29.97p/30p shares the sensor records but its encoder is not set up: do not record it.
- 60p, 120p, S&Q, HD, the Super 35 crop and Proxy Recording are not set up.
- **8K cannot record** while it is applied. A cold boot restores it.
- Keep the A1 II's own **De-Squeeze Display Off**. C3 runs the preview cycle in MOVIE instead of its assigned function.
- The viewfinder is not changed.
- Playback of the 3840 × 2560 clips on the camera is expected to work but has not been tried. Try ONE clip; if it cannot display it, do not retry.
- Whether the power switch alone removes the patch on the A1 II is not known. Keep the camera on during an apply.

## If something stops

Every stop prints a reason and says whether anything was sent. Please send that text.

- *the camera is in service mode but that device has no libusb driver yet*: do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 4.00 update*, or *DIFFERS from the 4.00 update*: not an A1 II on 4.00. Nothing further is sent.
- *The newest saved read-only check of this kit ... does not say READY*: run `check_readonly.cmd` (kit v3) first.
- *the stored records hold neither timing variant*: the camera's mode records are not what 4.00 computes. Nothing was written; send the folder.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/`: the scripts, the pinned program files and their source, the patch designs, and the emulations.
- `macos/`: `setup.command` and one `.command` per Windows launcher.
- `android/A1II-OpenGate.apk`: the phone app.
- `PORT_NOTES.md`: how the port was built, the runs so far, kits v2 and v3, the address map, the pins, and what is not known.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
