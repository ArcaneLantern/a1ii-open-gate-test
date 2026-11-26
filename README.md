# A1 II open gate: test kit v2 (firmware 4.00)

<p><b>Not working yet: this is a diagnosis kit.</b> The goal is the open gate that works on the A7 IV, A7S III and FX3, on the Sony A1 II (ILCE-1M2) firmware 4.00: a true 3840 × 2560 picture of the whole 3:2 sensor in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 23.98p (25p on a PAL camera), MP4 headers that say 3840 × 2560, the whole picture at 3:2 on the rear screen, and the C3 button cycling an anamorphic preview (3:2 → 2:1 → 2.25:1 → 2.4:1 → 3:2). Everything is written to the camera's memory only: a battery pull removes it.</p>

## What the first run showed (kit v1, 2026-11-26)

- **Every step applied correctly.** Every patch site held its new bytes afterwards, and the sensor really received the full-height window (its register copy showed the new values in the 4K mode).
- **In MOVIE the live view was wrong:** the picture sat too high, with a purple/black band across the bottom of the screen.
- **The camera then restarted:** about 15 seconds after entering MOVIE, or at once when recording started (red screen).
- **The camera's own log names the restart:** its image processor stops itself on purpose ("S-Ele Refresh ng force exception") when one stage of the picture pipeline has not finished for 11 frames in a row. The A7 IV hit the same stop during its own development, each time because a stage was told to expect more picture rows than it received.
- **What it means:** the lower part of each frame never arrives. The open question is why. There are two candidates:
  - the sensor does not deliver the full height in its 4K setting;
  - the full-height frame does not fit somewhere on the way.

  A third candidate was a size override in the A1 II's resize set-up (the cause of the same restart on the FX2). **It turned out not to be the cause:** in emulation it changes nothing in this state, at any SteadyShot margin. Test 3 still holds it off (step F16), but that is not a fix: **the full state is expected to fail exactly like the first run until test 0 and test 1 are reported.** For that reason kit v2 does not offer the full apply any more (`open_gate_apply` is withdrawn); test 3 and test 4 are the full state for when the tests point to a fix.

**Kit v2 takes the state apart, from the sensor alone upwards.** Please run **test 0 first**, then the others in order, each from a cold boot, and report what you see after each one.

## The tests

**SteadyShot OFF for every test.** If you also try Active, say so in the report.

| # | Launcher (Windows; macOS `.command` twins; Android: Test 0 to Test 4 buttons) | What it applies | What to look at in MOVIE |
|---|---|---|---|
| **0 (first)** | `test0_sensor_band.cmd` (put back: `test0_putback.cmd`) | **Only the sensor's window settings** at full height (and its read-out length). Every other table and the picture records stay stock, so the camera still takes a normal 16:9 picture, but now from the first lines the sensor sends | **The framing, compared with stock (see below).** "Moved": the sensor reads its full height. "Same": it does not. Also: any restart or purple band? |
| 1 | `test1_sensor_only.cmd` | **Only the sensor step:** the full-height window, squeezed into the stock 16:9 picture. Nothing else | If the sensor gives the full height: the whole sensor squeezed into the normal 16:9 view (things look about 16% shorter), **no purple/black band, no restart**. A recording gives a 3840 × 2160 file squeezed the same way. |
| 2 | `test2_real_rows_only.cmd` | **Only the real-rows sensor step:** the same window, every row kept through the first stage | A normal-looking 16:9 picture (the middle of the 3:2 frame), **no band, no restart**. A recording gives a normal 3840 × 2160 file. |
| 3 | `test3_squeeze_hold.cmd` (the full state; expected to fail like the first run for now) | Sensor (squeezed), F16, output size 3840 × 2560, encoder (HS, S, MP4 headers), XAVC S-I, rear screen 3:2, C3 cycle | The whole 3:2 picture filling the rear screen; C3 cycles the preview. Record 20 s in XAVC HS 4K 24p. |
| 4 | `test4_real_rows.cmd` (the full state, real rows) | The same with the real-rows sensor step (no F16 needed) | As test 3. |

**How to read test 0 (please do this carefully, it decides what comes next):**

1. Before the cold boot, in stock 4K 24p (MOVIE, nothing applied), put the camera on a **tripod** and frame a scene with something recognisable right at the **TOP edge** of the picture, for example the top of a door frame or a shelf. Note exactly what is at the top edge, or take a phone photo of the rear screen. Do not move the camera or the zoom from now on.
2. Cold boot, run `check_readonly.cmd`, then `test0_sensor_band.cmd`, and at the end set MOVIE as the script says.
3. Compare the rear screen with what you noted:
   - **Moved:** clearly MORE is visible above the old top edge (about 9% of the picture height), and less at the bottom. Then the sensor reads its full height. Report "moved".
   - **Same:** the framing is exactly as before. Then the sensor does not read beyond its 16:9 band in this setting. Report "same".
   - Also report any restart, and any purple or black band.

**Running a test:**

1. In the menu, set File Format XAVC HS 4K (or XAVC S 4K) at 24p (25p on a PAL camera). Turn S&Q, Proxy Recording, APS-C/Super 35, De-Squeeze Display and SteadyShot Off.
2. Set STILL, then **cold boot**: pull the battery for 10 seconds and switch on. Do not go to MOVIE yet.
3. Connect USB and run `check_readonly.cmd`. It must say VERDICT READY. Kit v2 needs a check made with kit v2; an older one does not count.
4. Run the test's launcher. It asks for the firmware version and a typed YES. Between steps it asks you to unplug and replug the USB cable. **Do not switch the camera off and do not pull the battery** until it says it has finished.
5. At the end the script asks for one more session, which only reads. Unplug USB, set MOVIE and watch the rear screen for at least 20 seconds. Note what you see, then plug in again. The script runs the debug dump itself.
6. Then unplug and try to record 10 seconds.

**After each test, report:**

- the test number;
- the rear screen in MOVIE: any purple or black band, and where? Is the framing normal, squeezed, or shifted?
- whether the camera restarted, and when: while you watched, when you pressed record, or not at all;
- whether a recording was made, and its size (MediaInfo, see below);
- the zipped `windows/camera_private` folder.

**If the camera restarts by itself**, do NOT pull the battery. The image processor keeps its own log across a restart, but not across a battery pull. Set STILL, connect USB, run `dump_info.cmd`, and only then cold boot for the next test. If the camera does not respond at all, pull the battery.

**What the answers tell us:**

- **Test 0 "same":** the sensor ignores the full-height window in its 4K setting; another sensor approach is needed (the picture fails because the lines never come).
- **Test 0 "moved" and no restart, but test 1 shows the band or restarts:** the sensor is fine; the taller frame does not fit somewhere between the sensor and the scaler.
- **Test 1 shows the band or restarts:** the problem is before the scaler (the sensor's window, or the taller frame on its way in), not the later steps.
- **Test 1 is clean but test 3 is not:** the problem is in the output-size, encoder or screen steps.
- **Test 2 differs from test 1:** that points at the squeeze.

The closing dump of kit v2 also reads the resize set-up's own record of what the second scaler expects, and the SteadyShot margin table. The report says outright whether the expected size **AGREES** with what the picture records deliver.

## All launchers

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 4.00 software the port was made from, and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | **The debug dump for testers.** Everything the check reads, plus: the camera's logs (kernel and image processor), the sensor's register state and window cells, the stored mode records (with the window they program), the resize set-up's view and margins (kit v2), and the display | No |
| `test0_sensor_band.cmd` … `test4_real_rows.cmd` | The five tests above, each followed by one read-only dump | **Yes: memory only** |
| `test0_putback.cmd` | Puts back test 0 only (after any other test use the put-backs below or a cold boot) | Yes: memory only |
| `open_gate_putback.cmd` | Puts every step back (after test 1, test 3 or kit v1's apply; a step that finds stock bytes says NOTHING TO DO) | Yes: memory only |
| `open_gate_putback_real_rows.cmd` | Puts every step back after test 2 or test 4 | Yes: memory only |
| `screen_putback.cmd` | Puts back only the screen and C3 steps | Yes: memory only |

The full-apply launchers of kit v1 (`open_gate_apply*.cmd`) are withdrawn; `a1m2_apply.py apply` now refuses and points to the tests.

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
3. Each Windows launcher has a macOS twin with the same name (`macos/test1_sensor_only.command` and so on). Each live run asks for your Mac password: it is needed to hand the camera's USB connection to the script.

If macOS refuses to open a .command file, open System Settings > Privacy & Security and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the file into the window, and press Return.

## Android

`android/A1II-OpenGate.apk` (version 0.3) runs this kit from a phone connected by USB-C. It carries exactly the files in `windows/tools` and runs them unchanged.

1. Set **USB Power Supply: Off** on the camera.
2. Press **1. Read-only check** first.
3. Then press **Test 0** first (**Put back Test 0** undoes it), then **Test 1** to **Test 4**, in order and each from a cold boot. The **Full apply** button only says that kit v2 uses the tests.
4. When the log says unplug and plug in again, do that with the phone cable. Never switch the camera off.
5. **Export logs** writes a zip to `Download/A1II-OpenGate/`: send it back.

## Checking a clip

- **MediaInfo:** `mediainfo --Output="Video;%Width%x%Height% original %Width_Original%x%Height_Original%" FILE` gives 3840x2160 after test 0, 1 or 2, and should give 3840x2560 with no "original" size after test 3 or test 4. ffprobe cannot show the header change: it reads the size from the stream.
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
- *The newest saved read-only check of this kit ... does not say READY*: run `check_readonly.cmd` (kit v2) first.
- *the stored records hold neither timing variant*: the camera's mode records are not what 4.00 computes. Nothing was written; send the folder.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/`: the scripts, the pinned program files and their source, the patch designs, and the emulations.
- `macos/`: `setup.command` and one `.command` per Windows launcher.
- `android/A1II-OpenGate.apk`: the phone app.
- `PORT_NOTES.md`: how the port was built, the first run, kit v2, the address map, the pins, and what is not known.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
