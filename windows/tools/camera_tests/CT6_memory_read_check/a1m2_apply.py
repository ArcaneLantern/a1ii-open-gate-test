"""A1 II (ILCE-1M2) firmware 4.00: apply, or put back, the open-gate state in the camera's MEMORY.

  python a1m2_apply.py apply    [--no-screen] [--no-meta] [--no-si] [--real-rows] [--dry-run]
  python a1m2_apply.py putback  [--no-screen] [--no-si] [--real-rows] [--dry-run]
  python a1m2_apply.py screen | screen-putback  [--dry-run]
  (apply and screen take --no-movie-session to leave out the closing read-only session)

The A1 II port (2026-11-26) of the open-gate state that works on the A7 IV, A7S III and FX3: a true 3840x2560 file of the whole 3:2 sensor,
shown at 3:2 on the rear screen, with the C3 button cycling an anamorphic preview. NOTHING OF THIS KIT HAS RUN ON AN A1 II. How it is built
(modding/A1M2_PORT.md and its part notes):
  - The A1 II reads its full-frame 4K picture 2x2-binned from a 16:9 band of the sensor (4320x2430). The sensor sets that band with two
    register-matrix cells (start block, half-height); L5 sets them to the full height in the 4K modes' own sensor setting (4320x2880, 3:2),
    keeps the 4K mode's line timing, and squeezes the taller picture into the stock 4320x2430 first-stage picture (the A7 IV's ogsq_v3 method),
    in the four drive modes that share the 4K picture records (0x820, 0x2820, 0x8c0, 0x28c0).
    --real-rows uses R5 instead: the same window, and the first scaler keeps all 2,880 rows (the second scaler then makes 3840x2560 at 1.125 on
    both axes: more vertical detail, less proven: the A7 IV ran it only after its squeezed form worked).
  - L16 makes the 4K output 3840x2560; L19 sets up the XAVC HS 4K and XAVC S 4K encoders and the MP4 headers for it; I19 does the same for
    XAVC S-I 4K (--no-si leaves it out).
  - S16 fills the 3:2 rear screen with the picture (and moves the focus-frame rectangles with it); C19 makes C3, in movie mode, cycle the
    preview 3:2 -> 2:1 -> 2.25:1 -> 2.4:1 -> 3:2 (de-squeeze for 1.33x, 1.5x and 1.6x anamorphic lenses; the file does not change).
  - No raw-write-buffer step: the A1 II's stock buffer already holds the taller first stage.

  apply    six steps, each its own USB session: L5 sensor side (ogsq_a1m2_v1), L16 output size (outsz2560_a1m2_v1), L19 encoder side
           (ogfile2560_hs_s_a1m2_v2), I19 XAVC S-I 4K (ogfilesi2560_a1m2_v1), S16 rear screen at 3:2 with the focus frames (lcdfill_a1m2_v1),
           C19 the C3 preview routine (lcdcycle_a1m2_v1). --no-screen leaves out S16 and C19; --no-meta uses N19 (the MP4 headers keep
           3840x2160); --no-si leaves out I19; --real-rows uses R5 for L5. A step that finds its bytes already applied says NOTHING TO DO
           and counts as passed.
  putback  the reverse: C20, S17, I20, L20, L17, L6 (R6 with --real-rows). A cold boot (battery out for 10 seconds) also undoes everything.
  screen / screen-putback   only the screen steps (S16, C19) or their put back (C20, S17).

The closing session (apply and screen): the script asks for Movie and an unplug and replug and runs the read-only dump itself, which reads
what the four stored records program (the window), the register matrix's window cells, the panel type, and the screen state. Nothing is
written in that session.

Rules it keeps:
- It starts only if the newest saved read-only check of this kit says VERDICT READY.
- It stops at the first step that does not end in DONE or NOTHING TO DO, and says what state that leaves.
- Each step is one pinned library; the runner (a1m2_run.py) refuses any other bytes.
Nothing is written to a firmware file or to the camera's settings. What is written lives in the running camera's memory. A cold
boot (battery out for 10 seconds) removes it. Whether the power switch alone removes it on the A1 II is not known (it did on the A7S III,
not on the A7 IV), so keep the A1 II switched on from the first step to the last.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CT1_usb_first_contact"))
sys.path.insert(0, str(HERE))
import ct1_common as c  # noqa: E402
import a1m2_run  # noqa: E402

FIRMWARE = a1m2_run.FIRMWARE
STEPS = {"apply": ("L5", "L16", "L19", "I19"), "putback": ("I20", "L20", "L17", "L6"), "screen": ("S16", "C19"), "screen-putback": ("C20", "S17")}
RUNNER = HERE / "a1m2_run.py"
LISTER = HERE.parent / "CT1_usb_first_contact" / "ct1_stage2_service.py"
STILL = "still images (the Still/Movie/S&Q switch under the mode dial on Still; the mode dial on P, A, S or M)"
MOVIE = ("Movie (the Still/Movie/S&Q switch on Movie; File Format XAVC HS 4K, XAVC S 4K or XAVC S-I 4K at 24p (23.98p), or 25p on a PAL camera; "
         "Proxy Recording off)")


def say(text=""):
    print(text, flush=True)


def sessions():
    """Saved sessions of this kit, newest first: (folder, manifest)."""
    root = c.PRIVATE_ROOT
    out = []
    if root.is_dir():
        for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
            try:
                out.append((folder, json.loads((folder / "manifest.json").read_text(encoding="utf8"))))
            except (OSError, ValueError):
                continue
    return out


def last_check():
    """The newest saved read-only check of this kit that fetched a result: (folder name, ready?) or None. A check that stopped before the
    camera answered says nothing and is skipped. A check made with another kit does not count: its header is not this helper's."""
    for folder, man in sessions():
        res = man.get("results", {})
        f = (res.get("ct6", {}).get("result") or {}).get("s3")
        if res.get("which") in ("check", "dump") and f:       # a dump makes every check the check makes, and gives the same verdict
            current = "a1m2read_v1 " in f.get("header", "") and "ILCE-1M2 4.00" in f.get("header", "")
            return folder.name, current and bool(f.get("ready")) and not f.get("identity_differs")
    return None


def last_result_sha():
    """The SHA-256 of the result the newest session fetched: the runner deletes a result left on the RAM disk only if it has this hash."""
    for _, man in sessions():
        try:
            return man["results"]["ct6"]["result"]["sha256"]
        except (KeyError, TypeError):
            continue
    return None


def usb_state():
    r = subprocess.run([sys.executable, "-I", "-B", str(LISTER), "--list"], capture_output=True, text=True, encoding="utf8", errors="replace", cwd=str(LISTER.parent))
    import re
    m = re.search(r"libusb sees: (\d+) Sony mass-storage device\(s\).*?, (\d+) Sony service device\(s\)", r.stdout)
    if not m:
        return "other"
    return "drive" if int(m.group(1)) == 1 and int(m.group(2)) == 0 else "service" if int(m.group(2)) else "other"


def wait_for_drive(first, timeout=600):
    asked, end = False, time.time() + timeout
    while usb_state() != "drive":
        if not asked:
            say()
            if first:
                say("The camera is not showing as a USB drive. Turn it on, set %s, connect USB (USB Connection Mode: Mass Storage (MSC))." % STILL)
            else:
                say(">>> Unplug the USB cable from the camera and plug it in again.")
                say(">>> Do NOT power the camera off or pull the battery: that would leave the steps half done.")
            say("Waiting for the camera (Ctrl+C to stop) ...")
            asked = True
        if time.time() > end:
            return False
        time.sleep(2)
    return True


def wait_for_replug(timeout=900):
    """Wait until the camera has been unplugged and shows up as a USB drive again. False on timeout."""
    end = time.time() + timeout
    while usb_state() != "other":                    # still plugged in, as a drive or in service mode
        if time.time() > end:
            return False
        time.sleep(1)
    while usb_state() != "drive":
        if time.time() > end:
            return False
        time.sleep(2)
    return True


def movie_session():
    """The closing read-only session, taken in movie mode."""
    say()
    say("=" * 78)
    say("One more session, and it only READS: it records what the camera holds after the apply, for the report.")
    say(">>> 1. Unplug the USB cable.")
    say(">>> 2. Set %s." % MOVIE)
    say("       Look at the rear screen for five seconds and remember it: the whole 3:2 picture, or anything odd (lines, colours, black parts)?")
    say("       Press C3 a few times: the picture should get narrower bands (2:1, 2.25:1, 2.4:1) and come back to 3:2.")
    say(">>> 3. Plug the USB cable in again, still in Movie.")
    say(">>> Do NOT switch the camera off: whether the power switch removes the patch on the A1 II is not known.")
    say("Waiting for the unplug and the replug (Ctrl+C to stop; the patch stays applied either way) ...")
    if not wait_for_replug():
        say("The camera did not come back as a USB drive. The steps are applied all the same.")
        return
    cmd = [sys.executable, "-I", "-B", str(RUNNER), "dump", "--go", "--firmware-shown", FIRMWARE]
    clear = last_result_sha()
    if clear:
        cmd += ["--clear-result", clear]
    rc = subprocess.run(cmd).returncode
    which, f = step_outcome()
    say()
    if rc or which != "dump" or not f:
        say("The read-only session did not finish. The steps are applied all the same.")
        return
    decoded = f.get("decoded") or {}
    w = (decoded.get("design_mode_windows") or {}).get("0x8c0")
    if w:
        say("The 4K 24p mode's stored record programs a %d-row window, band row %d (%s; stock 2430 rows from band row 222)." % (w["height"], w["band_row"], w["state"]))
    mc = decoded.get("matrix_column_2_window_cells")
    if mc:
        say("The sensor's window cells in the 4K setting: start block %s, half-height %s (%s; open gate 1 and 30)." % (mc["start_block"], mc["half_height"], mc["state"]))
    panel = (decoded.get("display") or {}).get("panel_types")
    if panel:
        say("The rear panel reports type %d (%s). Please send this folder: it settles the A1 II's panel shape." % (panel["rear"], panel["rear_aspect"]))
    say("(After --real-rows the read-only check counts the four picture records as OTHER and says NOT READY: that is expected, they hold R5's bytes.)")
    say(">>> Unplug USB now.")


def step_outcome():
    for _, man in sessions():
        f = man.get("results", {}).get("ct6", {}).get("result", {}).get("s3")
        return (man.get("results", {}).get("which"), f) if f else (None, None)
    return None, None


def plan(a):
    """The steps of one run, in order."""
    steps = STEPS[a.what]
    if a.no_meta:
        steps = tuple("N19" if k == "L19" else k for k in steps)
    if a.no_si:
        steps = tuple(k for k in steps if k not in ("I19", "I20"))
    if a.real_rows:
        steps = tuple({"L5": "R5", "L6": "R6"}.get(k, k) for k in steps)
    if a.what in ("apply", "putback") and not a.no_screen:
        steps = steps + STEPS["screen"] if a.what == "apply" else STEPS["screen-putback"] + steps
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=sorted(STEPS))
    ap.add_argument("--dry-run", action="store_true", help="show the steps and what each would send; nothing is sent")
    ap.add_argument("--no-screen", action="store_true", help="with apply or putback: without the screen steps (S16 and C19 / C20 and S17)")
    ap.add_argument("--no-movie-session", action="store_true", help="with apply or screen: leave out the closing read-only session in movie mode")
    ap.add_argument("--no-meta", action="store_true", help="with apply: the encoder step without the MP4 header heights (N19); the headers keep saying 3840x2160")
    ap.add_argument("--no-si", action="store_true", help="with apply or putback: without the XAVC S-I 4K step (I19 / I20)")
    ap.add_argument("--real-rows", action="store_true", help="with apply or putback: the real-rows sensor step (R5 / R6) instead of L5 / L6")
    a = ap.parse_args()
    whole = a.what in ("apply", "putback")
    if (a.no_screen or a.no_si or a.real_rows) and not whole:
        raise SystemExit("--no-screen, --no-si and --real-rows go with apply or putback. Nothing was sent.")
    if a.no_meta and a.what != "apply":
        raise SystemExit("--no-meta goes with apply (the put back L20 puts back either encoder step). Nothing was sent.")
    steps = plan(a)
    applying = a.what in ("apply", "screen")
    for k in steps:                                  # every library must be the pinned one before anything starts
        name, sha, _ = a1m2_run.WRITE_STEPS[k]
        p = a1m2_run.S3 / name
        if not p.is_file() or c.sha256(p.read_bytes()) != sha:
            raise SystemExit("%s is missing or is not the pinned build. Nothing was sent." % name)
    say("A1 II 4.00, %s: %d steps" % (a.what, len(steps)))
    for n, k in enumerate(steps, 1):
        say("  %d. %s  %s  (library %s...)" % (n, k, a1m2_run.WRITE_STEPS[k][2], a1m2_run.WRITE_STEPS[k][1][:16]))
    if applying and not a.no_movie_session:
        say("  then one read-only session (dump) in Movie: it records the state for the report. Nothing is written in it.")
    if a.dry_run:
        for k in steps:
            say()
            say("--- %s, what the session would send:" % k)
            r = subprocess.run([sys.executable, "-I", "-B", str(RUNNER), k, "--dry-run"], capture_output=True, text=True, encoding="utf8", errors="replace")
            say(r.stdout.rstrip() or r.stderr.rstrip())
        say()
        say("Dry run only: nothing was sent to any device.")
        return
    chk = last_check()
    if applying and (chk is None or not chk[1]):
        raise SystemExit("The newest saved read-only check of this kit %s. Run check_readonly first and get VERDICT READY. Nothing was sent."
                         % ("does not exist" if chk is None else "(%s) does not say READY" % chk[0]))
    say()
    say("This WRITES into the running camera's memory (not its firmware, not its settings).")
    if applying:
        say("NOTHING OF THIS KIT HAS RUN ON AN A1 II YET. The same method works on the A7 IV, A7S III and FX3; on the A1 II every step was")
        say("  checked against the A1 II's own firmware code and tables in emulation only. Possible outcomes are listed in README.md.")
        if a.real_rows:
            say("  --real-rows: the first scaler keeps all 2,880 rows. Try it only after the default (squeezed) apply has worked on your camera.")
    else:
        say("It has to follow an apply of this kit (with the same --no-si / --real-rows choices).")
    say("A cold boot (battery out for 10 seconds) returns the camera to stock. Whether the power switch alone does on the A1 II is not known:")
    say("so KEEP THE CAMERA SWITCHED ON from now until the script says it is finished.")
    if a.what == "apply":
        say("Before you go on: %s, a charged battery," % STILL)
        say("and a camera that was cold booted and has not been in Movie or S&Q since. (If it starts in Movie: set the switch to Still,")
        say("pull the battery for 10 seconds, put it back and switch on: it starts in stills.)")
        say("(If the open-gate state is already applied in this power-on, its steps will say NOTHING TO DO: that is fine.)")
    else:
        say("Before you go on: a charged battery, and %s." % STILL)
    if input("Firmware version in the camera's menu: ").strip() != FIRMWARE:
        raise SystemExit("Not %s. Nothing was sent." % FIRMWARE)
    if input("Type YES to write to the camera's memory: ").strip() != "YES":
        raise SystemExit("Not confirmed. Nothing was sent.")
    for n, k in enumerate(steps, 1):
        if not wait_for_drive(n == 1):
            raise SystemExit("The camera did not show up as a USB drive. Stopped before step %d (%s)." % (n, k))
        say()
        say("=" * 78)
        say("Step %d of %d: %s, %s" % (n, len(steps), k, a1m2_run.WRITE_STEPS[k][2]))
        cmd = [sys.executable, "-I", "-B", str(RUNNER), k, "--go", "--writes-memory", "--firmware-shown", FIRMWARE]
        clear = last_result_sha()
        if clear:
            cmd += ["--clear-result", clear]
        rc = subprocess.run(cmd).returncode
        which, f = step_outcome()
        if rc or which != k or not f or not f.get("ok"):
            say()
            say("STOPPED at step %d (%s): %s" % (n, k, "the session did not finish" if rc or which != k or not f else "outcome " + f["outcome"]))
            say("Steps before it are %s. To be sure of the camera's state: cold boot it (battery out for 10 seconds)." % ("applied" if applying else "put back"))
            say("Please send the newest folders in camera_private.")
            raise SystemExit(1)
    say()
    say("All %d steps passed (%s)." % (len(steps), a.what))
    if a.what == "apply":
        if a.no_meta:
            say("The files' MP4 headers say 3840x2160 (--no-meta): editors may open them squeezed; a remux to 3840x2560 fixes that.")
        else:
            say("The files' MP4 headers (tkhd, stsd, Sony's PROF) now say 3840x2560: editors should open them at 3:2 without a remux.")
            say("  Sony's XML (in the file and the sidecar) still says 3840x2160, 16:9.")
        say("8K CANNOT RECORD while this is applied (the encoder step gives the 8K class the 4K memory). A cold boot restores 8K.")
        say("In-camera playback of the 3840x2560 clips is expected to work (the A1 II opens playback with the A7 IV's 8K channel), but it")
        say("  is not traced end to end: try ONE clip, and if the camera says it cannot display it, do not retry; check clips on a computer.")
    if not a.no_screen and a.what in ("apply", "screen"):
        say("The screen steps: in Movie the rear screen (3:2, 2.1M dots) should now show the whole picture, filling it. A circle should look round.")
        say("  C3 cycles the preview 3:2 -> 2:1 (1.33x lens) -> 2.25:1 (1.5x) -> 2.4:1 (1.6x) -> 3:2, in Movie only; the file does not change.")
        say("  Keep the A1 II's own De-Squeeze Display OFF: while it is on, the camera uses its own ratio and the C3 states do not act.")
        say("  While this is applied C3 does not run the function assigned to it in Movie, and every 16:9 picture fills the screen.")
        say("  The viewfinder is not changed (it keeps the 16:9 squeezed preview).")
        say("  Please report: the screen in each C3 state (a photo of something round helps), and whether the focus frames sit right.")
    if applying:
        if a.no_movie_session:
            say(">>> BEFORE you unplug: set %s. Then unplug USB." % MOVIE)
        else:
            movie_session()
        say()
        say("Use only XAVC HS 4K, XAVC S 4K or XAVC S-I 4K at 24p (23.98p), or 25p on a PAL camera, while it is applied. 29.97p/30p shares")
        say("  the sensor's tall window and its picture records but its encoder is not set up: do not record it. Do not use 8K, 60p, 120p,")
        say("  S&Q, the Super 35 / APS-C crop or Proxy Recording.")
        say("If the camera stops or restarts: do NOT pull the battery yet. Set the switch to Still, replug USB and run dump_info, then send camera_private.")
        say("To return to stock: battery out for 10 seconds.")


if __name__ == "__main__":
    main()
