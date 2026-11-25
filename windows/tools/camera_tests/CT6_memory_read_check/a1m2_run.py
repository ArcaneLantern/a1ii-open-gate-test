"""A1 II (ILCE-1M2) firmware 4.00: run one of the two READ-ONLY helper libraries, or one write step, and save what it reports.

  python a1m2_run.py check --dry-run | --selftest
  python a1m2_run.py dump  --dry-run | --selftest
  python a1m2_run.py check --go --firmware-shown 4.00
  python a1m2_run.py dump  --go --firmware-shown 4.00 [--clear-result SHA256]
  python a1m2_run.py <write step> --go --writes-memory --firmware-shown 4.00      (a1m2_apply.py runs these)

  check   identity of the camera's software and what every site of the open-gate designs holds now: READY / NOT READY
          (the screen step's words are reported as well, not counted: it is optional)
  dump    the same, plus kernel and memory facts, the coprocessor's logs and some of its tables (sensor registers and the window cells of
          the register matrix, stored records, the scaler's state, the memory manager's records, the display: panel type, fit word,
          frame tables, the C3 routine's ratio constants)

Both read-only libraries only read. Each creates one file, its result, on the camera's RAM disk; this script fetches it. The
library is written to the camera's service partition, loaded once, and deleted again in the same session.

The A1 II counterpart of fx30_run.py (A1 II port, 2026-11-26): this camera's libraries, pins and result reader. The A1 II's main-processor
software is the A7 IV's family; its image processor's sensor tables and picture records are the A1's (the same sensor). Its sensor sets
the vertical window by two register-matrix cells, which the open gate changes in the 4K sensor mode's column (modding/A1M2_PORT.md).
"""
import argparse
import json
import platform
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CT1_usb_first_contact"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "helper"))
sys.path.insert(0, str(HERE / "helper_a1m2"))
import ct1_common as c  # noqa: E402
import ct6_level1_run as R  # noqa: E402

FIRMWARE, MODEL, BUILD = "4.00", "ILCE-1M2", "a1m2_400"
S3 = HERE / "helper_a1m2"                      # this kit's folder (the name S3 is kept from s3_run.py)
PINS = {"check": ("libJit_a1m2_check.so", "cc4bbcac0df1a71be64840b43d6a45895791be8147bba7f6bed1246ecd2895a1"),      # a1m2read_v1 (2026-11-26)
        "dump": ("libJit_a1m2_dump.so", "bef84fc975cf7775b51167634857f26bb61de46bfe791185f80e91e1eb8b4e83")}
LEVELS = {"check": 101, "dump": 102}              # numbers outside the A7 IV runner's own levels: none of its level-specific code runs
# THE WRITE STEPS. Each is one library built from the A7 IV helper's write code with this camera's tables (helper_a1m2/build_a1m2_write.sh).
# They change the running camera's memory until a cold boot. They are run through a1m2_apply.py, never by a launcher of the read-only kit.
WRITE_STEPS = {
    "L5": ("libJit_a1m2_L5.so", "0b3357a397e29eb193e7c50de522fbbbef393884a11b542bbd3ea463b28d6167",
           "apply the sensor-side design ogsq_a1m2_v1 (the 4K mode's 2x2-binned window made full height, 4320x2880, in modes 0x820/0x2820/0x8c0/0x28c0: "
           "3 register-matrix cells, 6 table spans, 4 picture records squeezed into the stock 4320x2430 front end, the 4 stored records with 27/32)"),
    "L6": ("libJit_a1m2_L6.so", "7188f400be220b4a2c7cf60221cc4a6027e4db820bb397e577ca3886b7d82279", "put back the sensor-side design ogsq_a1m2_v1"),
    # R5/R6: the real-rows alternative (ogh2880_a1m2_v1): the same window, the first scaler keeps all 2,880 rows (4320x2880 front end) and the second
    # scaler makes 3840x2560 at 1.125 on both axes. Apply with --real-rows instead of L5; R6 puts it back (L6 refuses R5's records, and the reverse).
    "R5": ("libJit_a1m2_R5.so", "fcb27cdbf129fb4f1f411f3dfee03b322c8751748d1b11354671e6630ee82ae6",
           "apply the sensor-side design ogh2880_a1m2_v1 (the same full-height window; the first scaler keeps every row: 4320x2880 front end)"),
    "R6": ("libJit_a1m2_R6.so", "933e176ac348e76b6f4d2553c9590e67fc24d5e674d4339f8d159b1083ab6c24", "put back the sensor-side design ogh2880_a1m2_v1"),
    "L16": ("libJit_a1m2_L16.so", "2f09b46b607794fae3479d9bef9f8aad228546012ab145a859025f3a74acbfba", "apply the output size outsz2560_a1m2_v1 (one word)"),
    "L17": ("libJit_a1m2_L17.so", "2f5516ddd577bcc679120a4fef68fe3acc6ff3c292ab28daa238c9c031b56ab4", "put back the output size outsz2560_a1m2_v1"),
    # L19: the encoder side with the MP4 header heights (ogfile2560_hs_s_a1m2_v2: tkhd, stsd and Sony's PROF say 3840x2560). L20 puts back
    # either version. N19 = the same without the heights (apply --no-meta).
    "L19": ("libJit_a1m2_L19.so", "88c96675d996b9c1c4ef54dcbf94bde59e2fc05a848bf6f5f05630ca33eb4d2e", "apply the encoder-side design ogfile2560_hs_s_a1m2_v2 (101 + 4 sites, and the MP4 headers say 3840x2560: 2 more)"),
    "L20": ("libJit_a1m2_L20.so", "93c9a6427b098883c79b9e8b19bf4beb6603f6e56fcb70e603db8d084f9f500b", "put back the encoder-side design ogfile2560_hs_s_a1m2_v2 (or v1)"),
    "N19": ("libJit_a1m2_N19.so", "3e6304d5ca9bd42ed6a9e1f14bce71f0dcba0a7d2b03d8db29bd0edfab1669fa", "apply the encoder-side design ogfile2560_hs_s_a1m2_v1 (101 + 4 sites; the MP4 headers keep 3840x2160)"),
    # I19/I20: XAVC S-I 4K at 3840x2560 (ogfilesi2560_a1m2_v1, the FX3 kit's I step on the A1 II's tables): the last encoder step of the apply.
    "I19": ("libJit_a1m2_I19.so", "bf3d88bc8bc621007bd51d13d208b8a9350f64e5b91187d00ea4971101c77018", "apply XAVC S-I 4K at 3840x2560: ogfilesi2560_a1m2_v1 (the S-I encoder request, 4 descriptors and their profiles: 16 + 1 sites)"),
    "I20": ("libJit_a1m2_I20.so", "0390c9179ce8daa7c273c91bba187118118a3500eec25eac02d8528f2e213d83", "put back XAVC S-I 4K: ogfilesi2560_a1m2_v1"),
    # The rear-screen steps (optional, on top of the open-gate state): S = the level 16/17 code with the screen words, C = the C3 preview routine
    # in appFw.so (levels 19/20 with MP_LIB appFw.so: the routine in the zero tail of appFw's first segment, then one branch to it).
    "S16": ("libJit_a1m2_S16.so", "a4d4c8011c30f06f433b11e2011c1b40d0430f9e13a383fb6272719991a5587d", "apply the screen words lcdfill_a1m2_v1 (the 3:2 rear screen filled with the whole picture, and the three focus-frame rectangles: 7 words)"),
    "S17": ("libJit_a1m2_S17.so", "3849213c9560131ec523c26f4d55e1c7ab48d094a6687f4039097eaf5fe7b070", "put back the screen words lcdfill_a1m2_v1"),
    "C19": ("libJit_a1m2_C19.so", "a42eef38bdea70763faeac4c1d9a5c207fe5eacbe87c3719cbdef83644dda0eb", "apply the C3 preview routine lcdcycle_a1m2_v1 (3:2, 2:1, 2.25:1, 2.4:1; code in appFw.so: the routine, then one branch to it)"),
    "C20": ("libJit_a1m2_C20.so", "c3167a72f599033619ca3171c8d77822632934833e158c1d1f78d2e1f7a78c38", "put back the C3 preview routine lcdcycle_a1m2_v1"),
}
PINS.update({k: v[:2] for k, v in WRITE_STEPS.items()})
LEVELS.update({k: {"L": 200, "S": 300, "C": 400, "N": 500, "I": 700, "R": 800}[k[0]] + int(k[1:]) for k in WRITE_STEPS})
WHICH = "check"
DESIGN_MODES = ("0x820", "0x2820", "0x8c0", "0x28c0")

def write_result(data):
    """The facts of a write step's result (the A7 IV helper's report format)."""
    import hashlib
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    pick = lambda start: next((ln for ln in lines if ln.startswith(start)), None)
    outcome = ("UNDO INCOMPLETE" if pick("!! UNDO INCOMPLETE") or pick("UNDO INCOMPLETE") else "DONE" if pick("DONE: ") else "NOTHING TO DO" if pick("NOTHING TO DO") else
               "NOT DONE (everything put back)" if pick("NOT DONE: ") else "NOTHING WRITTEN" if any("nothing is written" in ln for ln in lines) else "UNKNOWN")
    problems = [ln for ln in lines if ln.startswith("!!")]
    variant = pick("the stored records are the ")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": lines[0].startswith("readcheck 1 level %s" % WHICH[1:]),
            "euid": "see the result", "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(problems),
            "complete": any(ln.startswith("== done") for ln in lines[-3:]),
            "s3": {"step": WHICH, "what": WRITE_STEPS[WHICH][2], "outcome": outcome, "ok": outcome in ("DONE", "NOTHING TO DO"),
                   "outcome_line": pick("DONE: ") or pick("NOTHING TO DO") or pick("NOT DONE: ") or pick("!! UNDO INCOMPLETE") or pick("UNDO INCOMPLETE"),
                   "timing_variant": variant, "problem_lines": problems}}


def reference():
    return json.loads((S3 / "a1m2_reference.json").read_text(encoding="utf8"))


def expected():
    return json.loads((S3 / "a1m2_expected.json").read_text(encoding="utf8"))


# ------------------------------------------------------------ reading a result

def check_result(data):
    """The facts of a result file. Keys the A7 IV runner prints, plus this helper's own under "s3"."""
    if WHICH in WRITE_STEPS:
        return write_result(data)
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    head = lines[0] if lines else ""
    count = lambda pat: sum(1 for ln in lines if re.search(pat, ln))
    verdict = next((ln for ln in lines if ln.startswith("VERDICT ")), "no verdict line")
    pages = {}
    for ln in lines:
        if ln.startswith("cppage "):
            _, name, addr, hx = ln.split(" ", 3)
            pages[int(addr, 16)] = (name, bytes.fromhex(hx.strip()))
    sites, other = [], {}
    for ln in lines:
        m = re.match(r"site (\S+) (0x[0-9a-f]+) len (\d+)(?: bytes (?:differing from stock )?(\S+))?  (STOCK|TARGET|OTHER.*|NOT READ)$", ln)
        if m:
            sites.append({"name": m.group(1), "address": m.group(2), "length": int(m.group(3)), "shown": m.group(4), "state": m.group(5)})
        m = re.match(r"other (\S+) ([0-9a-f]+)$", ln)
        if m:
            other[m.group(1)] = bytes.fromhex(m.group(2))
    s3 = {"header": head, "verdict": verdict, "ready": verdict.startswith("VERDICT READY"),
          "identity_same": count(r"SAME as the 6\.01 update$"), "identity_differs": count(r"DIFFERS from the 6\.01 update$"),
          "coprocessor_sites": sites, "libmpr_sites": [ln for ln in lines if ln.startswith("lm ")],
          "avcam_stock": count(r"^av .*  STOCK$"), "avcam_target": count(r"^av .*  TARGET$"), "avcam_other": count(r"^av .*  OTHER$"),
          "avcam_guards": [ln for ln in lines if ln.startswith("guard ")], "problem_lines": [ln for ln in lines if ln.startswith("!!")],
          "pages": len(pages)}
    s3["stored_records"] = stored_record_states(sites, other)
    cmd = re.search(r"== file /proc/cmdline\n(.*?)\n== end", text, re.S)
    ver = re.search(r"== file /proc/version\n(.*?)\n== end", text, re.S)
    s3["kernel_command_line"], s3["kernel_version"] = (cmd.group(1).strip() if cmd else None), (ver.group(1).strip() if ver else None)
    if pages:
        s3["decoded"] = decode_pages(pages)
    import hashlib
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": head.startswith("a1m2read ") and "ILCE-1M2 4.00" in head, "euid": "not read",
            "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(s3["problem_lines"]), "complete": "== done" in lines[-3:],
            "s3": s3, "_pages": pages}


def record_state(mode, rec):
    """What one stored record holds at the design's offsets: stock, applied (L5) or applied real rows (R5), and in which timing variant
    (NTSC 60 Hz / PAL 50 Hz)."""
    ref = reference()
    for label, sr in (("applied", ref["stored_records_design"][mode]), ("applied real rows", ref["stored_records_design_real_rows"][mode])):
        offs = [int(x, 16) for x in sr["offsets_that_differ"]]
        got = bytes(rec[k] for k in offs)
        for v in ("ntsc", "pal"):
            for what, key in (("stock", "stock"), (label, "design")):
                if got == bytes(bytes.fromhex(sr[v][key])[k] for k in offs):
                    return f"{what} ({v.upper()})"
    return "other"


def stored_record_states(sites, other):
    out = {}
    for s in sites:
        if not s["name"].startswith("stored_record_"):
            continue
        mode = s["name"][len("stored_record_"):]
        if s["state"] in ("STOCK", "TARGET"):
            out[mode] = "stock (NTSC)" if s["state"] == "STOCK" else "applied (NTSC)"
        elif s["name"] in other:
            out[mode] = record_state(mode, other[s["name"]])
        else:
            out[mode] = "not read"
    return out


def decode_pages(pages):
    """What the dump's coprocessor pages say, set against the firmware file's tables."""
    ref, out = reference(), {}

    def mem(addr, n):
        b = bytearray()
        while n:
            page = pages.get(addr & ~0xFFF)
            if page is None:
                return None
            take = min(n, 4096 - (addr & 0xFFF))
            b += page[1][addr & 0xFFF:(addr & 0xFFF) + take]
            addr, n = addr + take, n - take
        return bytes(b)

    # the sensor register shadow against each column of the register matrix (28 columns; the open gate changes three cells of column 2, the
    # column of the four 4K modes, in place: start block 6 -> 1, half-height 25 -> 30, register +0x90 58 -> 63)
    rows = [(a, bytes.fromhex(h)) for a, h in ref["matrix"]]
    ncol = ref["matrix_columns"]
    shadow = [(a, mem(a, 1)) for a, _ in rows]
    if all(v is not None for _, v in shadow):
        score = [sum(1 for (a, cols), (_, v) in zip(rows, shadow) if cols[k] == v[0]) for k in range(ncol)]
        best = max(range(ncol), key=lambda k: score[k])
        users = [ref["mode_ids"][i] for i, col in enumerate(ref["column_map"]) if col == best]
        out["sensor_registers"] = {"rows": len(rows), "rows_equal_per_column": score, "closest_column": best, "modes_using_it": users,
                                   "columns_with_the_same_score": [k for k in range(ncol) if score[k] == score[best]],
                                   "rows_differing_from_it": [[i, hex(a), cols[best], v[0]] for i, ((a, cols), (_, v)) in enumerate(zip(rows, shadow)) if cols[best] != v[0]][:64]}
        cells = {}
        for name, c in ref["window_cells"].items():
            a = rows[c["row"]][0]
            cells[name] = {"shadow": shadow[c["row"]][1][0], "stock": c["stock"], "open_gate": c["open_gate"]}
        out["sensor_window_registers_now"] = cells
    m0 = int(ref["matrix_address"], 16)
    got = mem(m0, ref["matrix_row_bytes"] * len(rows)) if (m0 & ~0xFFF) in pages else None
    if got is not None:
        want = b"".join(struct.pack("<I", a) + cols for a, cols in rows)
        out["matrix_equals_file"] = got == want
        col2 = {name: got[ref["matrix_row_bytes"] * c["row"] + 4 + ref["open_gate_column"]] for name, c in ref["window_cells"].items()}
        state = "stock" if all(col2[n] == c["stock"] for n, c in ref["window_cells"].items()) else \
            "open gate" if all(col2[n] == c["open_gate"] for n, c in ref["window_cells"].items()) else "other"
        out["matrix_column_2_window_cells"] = dict(col2, state=state)
    # the stored drive-parameter records against the emulated ones, and the window the four design modes' records program
    r0, size = int(ref["records_address"], 16), ref["record_size"]
    recs, window = {}, {}
    wo = {k: int(v, 16) for k, v in ref["window"]["record_offsets"].items()}
    for i, mid in enumerate(ref["mode_ids"]):
        b = mem(r0 + i * size, size)
        if b is None:
            continue
        emu = bytes.fromhex(ref["emulated_stock_records"][mid])
        diff = [o for o in range(size) if b[o] != emu[o]]
        recs[mid] = {"index": i, "all_zero": not any(b), "bytes_differing_from_emulation": len(diff), "offsets": [hex(o) for o in diff[:48]], "record": b.hex()}
        if mid in DESIGN_MODES:
            u = lambda k: struct.unpack_from("<H", b, wo[k])[0]
            s = wo["sampling_ratio"]
            window[mid] = {"state": record_state(mid, b), "height": u("height"), "pdaf_rows": u("pdaf_rows"), "band_row": u("band"),
                           "lc": [u("lc4"), u("lc6")], "readout_line_periods": u("readout_length"), "sampling_ratio": [b[s], b[s + 1], b[s + 2], b[s + 3]]}
    out["stored_records"] = recs
    out["design_mode_windows"] = window
    t = mem(int(ref["size_table_address"], 16), 128)
    if t is not None:
        out["size_table"] = [list(struct.unpack_from("<HHI", t, 8 * k)) for k in range(16)]
    # The resize module: its A1 II addresses are weak (port_addr from the FX2's, 1-2 votes): the decoder searches the pages for known sizes.
    st, seen = {}, {}
    pairs = {(4320, 2880), (4320, 2430), (4332, 2896), (4332, 2446), (4320, 2442), (4320, 2446), (3840, 2560), (3840, 2160), (2204, 2442), (2204, 2446),
             (2204, 2896), (2172, 2442), (1920, 1080)}
    for addr, (name, blob) in sorted(pages.items()):
        if name not in ("resizework", "resizestate"):
            continue
        for o in range(0, 4096 - 3, 2):
            p = struct.unpack_from("<HH", blob, o)
            if p in pairs:
                seen.setdefault("%dx%d" % p, []).append(hex(addr + o))
    st["where_sizes_occur"] = {k: v[:40] for k, v in sorted(seen.items())}
    if any(n in ("resizework", "resizestate") for n, _ in pages.values()):
        out["scaler_state"] = st
    # The display (modding/A1M2_PORT_SCREEN.md): panel-type bytes rear 0x1a1c638 (3 = 3:2 expected), viewfinder 0x1a1c768; the fit word of a
    # 16:9 picture on the 3:2 panel 0x1faca4 (3 letterbox stock, 0 fill with the screen step); the three frame tables' 3:2-panel 16:9 entries;
    # the letterbox constants the C3 routine writes per state (0x1fafa4 / 0x1fafa8).
    disp = {}
    types = mem(int(ref["panel_type"]["rear"], 16), 1), mem(int(ref["panel_type"]["evf"], 16), 1)
    if None not in types:
        name = {1: "16:9", 2: "4:3", 3: "3:2"}
        disp["panel_types"] = {"rear": types[0][0], "rear_aspect": name.get(types[0][0], "unknown"), "evf": types[1][0], "evf_aspect": name.get(types[1][0], "unknown")}
    fit = mem(0x1FACA4, 4)
    if fit is not None:
        v = struct.unpack_from("<I", fit)[0]
        disp["fit_16x9_on_3x2_panel"] = {"word": v, "state": {3: "letterbox (stock)", 0: "fill (screen step applied)"}.get(v, "other")}
    rc = mem(0x1FAFA4, 8)
    if rc is not None:
        disp["c3_ratio_constants"] = rc.hex()
    rws = {}
    for w in ref["screen_words"]:
        a = int(w["address"], 16)
        b = mem(a, 4)
        if b is not None:
            rws[w["address"]] = "stock" if b.hex() == w["stock"] else "applied" if b.hex() == w["new"] else "other " + b.hex()
    if rws:
        disp["screen_words"] = {"stock": sum(v == "stock" for v in rws.values()), "new": sum(v == "applied" for v in rws.values()),
                                "other": sum(v.startswith("other") for v in rws.values()), "each": rws}
    if disp:
        out["display"] = disp
    return out


# ------------------------------------------------------------ the A7 IV runner, pointed at this camera

def known_answer(session, camera):
    want = (S3 / "DeviceInfo.xml").read_bytes()
    there, data = R.read(camera, R.KNOWN_PATH)
    if not there or data != want:
        raise c.StopTest("DeviceInfo.xml is not the file of the 4.00 update (%s); nothing else is sent"
                         % ("the camera returned no file" if not there else "%d bytes, SHA-256 %s" % (len(data), c.sha256(data)[:16])))
    session.say("Known-answer read: DeviceInfo.xml equals the 4.00 file (the A7 IV, A1 and others have the same file: the helper itself checks which camera this is)")


def run_helper(data):
    """What loading the uploaded bytes gives on a model A1 II: the real AArch64 code in Unicorn if it is installed, else a canned text."""
    if WHICH in WRITE_STEPS:                        # the write libraries are emulated by helper_a1m2/emu_a1m2_write.py; here only the session flow is simulated
        text = "readcheck 1 level %s\neuid 0\n== level %s\nDONE: every site holds the target bytes (canned)\n== done, bytes written before this line: 0\n" % (WHICH[1:], WHICH[1:])
        return text.encode(), "canned"
    try:
        import emu_a1m2
    except Exception:
        text = "a1m2read a1m2read_v1 %s for ILCE-1M2 4.00; read-only\n== file /proc/version\nLinux (simulated)\n\n== end 18 bytes\n== summary\nVERDICT READY (canned)\n== done\n" % WHICH
        return text.encode(), "canned"
    r, text = emu_a1m2.run(bytes(data))
    if r.bad:
        raise AssertionError("the emulated helper stopped: %s" % r.bad)
    return text.encode(), "emulated"


def make_sim(lib, files=None, fault=None):
    sim = _make_sim(lib, files, fault)
    if "/usr/share/pmbp/DeviceInfo.xml" not in (files or {}):
        sim.fs["/usr/share/pmbp/DeviceInfo.xml"] = (S3 / "DeviceInfo.xml").read_bytes()
    return sim


def use(which):
    """Point the runner's module state at one of this camera's libraries."""
    global WHICH
    WHICH = which
    name, sha = PINS[which]
    if not (S3 / name).is_file():
        raise SystemExit("%s is not in this kit%s. Nothing was sent." % (name, " (the write steps are not published yet)" if which in WRITE_STEPS else ""))
    R.LEVEL, R.DESIGN, R.LIB, R.LIB_SHA256 = LEVELS[which], "og4k_data_v1", S3 / name, sha
    R.check_result, R.known_answer, R.run_helper, R.make_sim = check_result, known_answer, run_helper, make_sim
    c.EXPECTED_FIRMWARE = FIRMWARE
    return R.library()


_make_sim = R.make_sim


def selftest(lib):
    done = []

    def check(cond, what):
        if not cond:
            raise AssertionError("self-test failed: " + what)
        done.append(what)

    W, D = "SET_FILE2", "FILE_DELETE2"
    s, sim, stopped = R.simulate(lib, R.body_run)
    r = s.results.get("ct6", {})
    check(not stopped and not sim.unexpected and R.sent(s).count(W) == 1 and R.sent(s).count(D) == 1, "normal run: one write, one delete, nothing off the list")
    check(R.sent(s).index(D) < len(R.sent(s)) - 2 and R.sent(s)[-1] == "GET_FILE2", "normal run: the delete comes before the result is read")
    check(R.LIB_PATH.decode() not in sim.fs and sim.loads == 1, "normal run: the library was loaded once and is gone afterwards")
    f = r.get("result", {}).get("s3", {})
    if WHICH in WRITE_STEPS:
        check(f.get("ok") and r["result"]["header_ok"], "normal run: the step's result is read as DONE")
    else:
        check(f.get("ready") and not f.get("identity_differs"), "normal run: the %s helper reports a stock 4.00 camera as READY" % sim.how)
    if sim.how == "emulated":
        check(len(f["coprocessor_sites"]) == len(expected()["cp_sites"]) == 27 and f["avcam_stock"] == 101 and len(f["libmpr_sites"]) == expected()["lm_sites"] == 6,
              "normal run: every coprocessor site, 6 libmpr (4 rows, 2 MP4 header heights) and 101 av-cam sites are reported")
        check(f.get("stored_records") == {m: "stock (NTSC)" for m in DESIGN_MODES}, "normal run: the four stored records read as stock (NTSC)")
        if WHICH == "dump":
            d = f.get("decoded", {})
            check(d.get("matrix_equals_file") and len(d.get("stored_records", {})) == 44 and d.get("size_table"), "dump: the pages decode (matrix, 44 records, size table)")
            check(d.get("matrix_column_2_window_cells", {}).get("state") == "stock", "dump: the register matrix's column 2 holds the stock 16:9 window cells")
            check(all(v["height"] == 2430 and v["band_row"] == 222 and v["state"] == "stock (NTSC)" for v in d.get("design_mode_windows", {}).values())
                  and len(d.get("design_mode_windows", {})) == 4, "dump: the four design modes' records program the stock 4320x2430 window, band row 222")
            dp = d.get("display", {})
            check(dp.get("fit_16x9_on_3x2_panel", {}).get("state") == "letterbox (stock)" and dp.get("screen_words", {}).get("stock") == 7
                  and "panel_types" in dp and "c3_ratio_constants" in dp,
                  "dump: the display pages decode (fit word, the 7 screen words, panel types, the C3 ratio constants)")
    s, sim, stopped = R.simulate(lib, R.body_run, files={R.LIB_PATH.decode(): b"someone else's"})
    check(stopped and W not in R.sent(s) and D not in R.sent(s), "a foreign libJit.so on the camera: stops, nothing written, nothing deleted")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp_wbshd/readcheck_result.txt": b"old"})
    check(stopped and W not in R.sent(s), "a result already on the RAM disk: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp/jbusy": b""})
    check(stopped and W not in R.sent(s), "/tmp/jbusy present: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/usr/share/pmbp/DeviceInfo.xml": b"<other camera/>"})
    check(stopped and len(R.sent(s)) == 2, "another DeviceInfo.xml: stops after the known-answer read")
    s, sim, stopped = R.simulate(lib, R.body_run, fault="load")
    check(stopped and R.sent(s).count(D) == 1 and R.LIB_PATH.decode() not in sim.fs, "a camera that cannot load the library: it is still deleted")
    check(len(R.refusals(lib)) == 15, "the guard refuses the 15 listed packets (changed library, other paths, backup, flash and debug writes ...)")
    return done


def report(session, facts, which):
    f = facts["s3"]
    if which in WRITE_STEPS:
        lines = ["A1 II 4.00 step %s: %s" % (which, f["what"]), "OUTCOME: %s" % f["outcome"], str(f["outcome_line"])]
        if f.get("timing_variant"):
            lines.append(f["timing_variant"])
        lines += ["  " + ln for ln in f["problem_lines"]]
        session.save_bytes("a1m2_report.txt", ("\n".join(lines) + "\n").encode())
        for ln in lines:
            session.say(ln)
        return
    lines = ["A1 II 4.00 %s, %s" % (which, time.strftime("%Y-%m-%d %H:%M:%S")), f["header"], f["verdict"],
             "identity: %d same, %d differ" % (f["identity_same"], f["identity_differs"]),
             "kernel: %s" % f["kernel_version"], "command line: %s" % f["kernel_command_line"]]
    for s in f["coprocessor_sites"]:
        lines.append("  coprocessor %-22s %s len %-4d %s%s" % (s["name"], s["address"], s["length"], s["state"], "" if s["shown"] is None else "  (" + s["shown"] + ")"))
    lines.append("stored records of the four open-gate modes: " + ", ".join("%s %s" % kv for kv in f.get("stored_records", {}).items()))
    lines += ["  " + ln for ln in f["libmpr_sites"]] + ["  " + ln for ln in f["avcam_guards"]]
    lines.append("  av-cam.bin sites: %d stock, %d target, %d other" % (f["avcam_stock"], f["avcam_target"], f["avcam_other"]))
    lines += ["problem lines:"] + ["  " + ln for ln in f["problem_lines"]] if f["problem_lines"] else ["no problem lines"]
    d = f.get("decoded")
    if d:
        sr = d.get("sensor_registers")
        if sr:
            lines.append("sensor register shadow: closest matrix column %d (%d of %d rows equal; columns with the same score %s; modes %s)"
                         % (sr["closest_column"], sr["rows_equal_per_column"][sr["closest_column"]], sr["rows"], sr["columns_with_the_same_score"], ", ".join(sr["modes_using_it"])))
        lines.append("register matrix equals the file: %s" % d.get("matrix_equals_file"))
        mc = d.get("matrix_column_2_window_cells")
        if mc:
            lines.append("register matrix column 2 (the 4K modes' sensor settings): start block %s, half-height %s, register +0x90 %s -> %s"
                         % (mc["start_block"], mc["half_height"], mc["reg_0x90"], mc["state"]))
        sw = d.get("sensor_window_registers_now")
        if sw:
            lines.append("sensor register shadow now: " + ", ".join("%s %d (stock %d, open gate %d)" % (k, v["shadow"], v["stock"], v["open_gate"]) for k, v in sw.items()))
        zero = [m for m, v in d.get("stored_records", {}).items() if v["all_zero"]]
        same = [m for m, v in d.get("stored_records", {}).items() if not v["bytes_differing_from_emulation"]]
        lines.append("stored drive-parameter records: %d read, %d equal to the emulated ones, %d all zero" % (len(d.get("stored_records", {})), len(same), len(zero)))
        for m, v in d.get("design_mode_windows", {}).items():
            lines.append("  mode %s: %s; window %d rows, band row %d, %d phase-detect rows, LC %s, read-out %d line periods, sampling %s"
                         % (m, v["state"], v["height"], v["band_row"], v["pdaf_rows"], v["lc"], v["readout_line_periods"], v["sampling_ratio"]))
        if d.get("size_table"):
            lines.append("movie size table: " + "; ".join("%dx%d id %#x" % tuple(r) for r in d["size_table"]))
        ss = d.get("scaler_state")
        if ss:
            lines.append("resize pages (weak addresses; known sizes found):")
            for k, v in ss.get("where_sizes_occur", {}).items():
                lines.append("  %s at %s%s" % (k, ", ".join(v[:10]), " ..." if len(v) > 10 else ""))
        dp = d.get("display")
        if dp:
            lines.append("display (what the screen and C3 steps change):")
            if "panel_types" in dp:
                t = dp["panel_types"]
                lines.append("  panel types: rear %d (%s), viewfinder %d (%s)" % (t["rear"], t["rear_aspect"], t["evf"], t["evf_aspect"]))
            if "fit_16x9_on_3x2_panel" in dp:
                lines.append("  fit word of a 16:9 picture on the 3:2 panel: %(word)d, %(state)s" % dp["fit_16x9_on_3x2_panel"])
            if "c3_ratio_constants" in dp:
                lines.append("  C3 routine's letterbox constants (0x1fafa4): %s" % dp["c3_ratio_constants"])
            if "screen_words" in dp:
                lines.append("  screen step words: %(stock)d stock, %(new)d applied, %(other)d other" % dp["screen_words"])
    session.save_bytes("a1m2_report.txt", ("\n".join(lines) + "\n").encode())
    for ln in lines[:8] + lines[-6:]:
        session.say(ln)


def last_saved_sha():
    """The SHA-256 of the result the newest saved session of this kit fetched, or None."""
    root = c.PRIVATE_ROOT
    if not root.is_dir():
        return None
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
        try:
            return json.loads((folder / "manifest.json").read_text(encoding="utf8"))["results"]["ct6"]["result"]["sha256"]
        except (OSError, KeyError, TypeError, ValueError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=sorted(PINS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--remove-only", action="store_true")
    ap.add_argument("--clear-result", metavar="SHA256", help="first delete the result file of an earlier run from the RAM disk, only if its SHA-256 is this")
    ap.add_argument("--firmware-shown")
    ap.add_argument("--writes-memory", action="store_true", help="needed for a write step (L5, L6, R5, R6, L16, L17, L19, L20, N19, I19, I20, S16, S17, C19, C20): it changes the running camera's memory")
    a = ap.parse_args()
    if a.which in WRITE_STEPS and a.go and not (a.dry_run or a.selftest) and not a.writes_memory:
        raise SystemExit("%s is a write step: %s. It needs --writes-memory as well. Use a1m2_apply.py. Nothing was sent." % (a.which, WRITE_STEPS[a.which][2]))
    lib = use(a.which)
    if a.dry_run or a.selftest:
        if a.selftest:                              # --dry-run and --selftest win over --go (the launchers always pass --go): nothing is sent
            for line in selftest(lib):
                print("PASS  " + line)
            print("all checks passed; nothing was sent to any device")
        else:
            print("\n".join(R.dry_run_lines(lib)))
        return
    if not a.go or a.firmware_shown != FIRMWARE:
        raise SystemExit("A live run needs --go and --firmware-shown %s (the version the camera's menu shows). Nothing was sent." % FIRMWARE)
    R.refusals(lib)
    selftest(lib)                                   # the flow must pass on the simulated camera on the day, before the real one
    import ct1_stage2_service as service
    R.CLEAR_SHA = a.clear_result or last_saved_sha()
    body = R.body_remove_only if a.remove_only else R.body_run
    with c.Session("remove_only" if a.remove_only else "a1m2_%s" % a.which, test="CT6") as session:
        session.results.update(firmware_shown_on_camera=a.firmware_shown, model=MODEL, which=a.which, library_sha256=PINS[a.which][1],
                               pc={"platform": platform.platform(), "python": sys.version.split()[0]})
        inner = service.connect(session)
        try:
            R.service_session(session, inner, lambda cam: body(session, cam, lib), lib)
            facts = session.results.get("ct6", {}).get("result")
            if facts and not a.remove_only:
                pages = facts.pop("_pages", {})
                for addr, (name, blob) in sorted(pages.items()):
                    session.save_bytes("cp_%s_%08x.bin" % (name, addr), blob)
                report(session, facts, a.which)
        finally:
            time.sleep(3)
            c.print_pnp(session, "after the stop request")
            out = session.results.get("ct6", {})
            print("Library sent: %s. On the camera now: %s." % (
                "yes" if out.get("library_sent") else "no",
                {False: "no (confirmed)", True: "YES", None: "not sent" if not out.get("library_sent") and not a.remove_only else "UNKNOWN"}[out.get("library_on_camera_after")]))
            if a.which in WRITE_STEPS:
                print("This was a WRITE step. A cold boot (battery out for 10 seconds) undoes everything written. Whether the power switch alone does on the A1 II is not known: keep the camera on between steps.")
            else:
                print("Nothing on the camera was changed. Unplug and replug the USB cable before another run; a cold boot (battery out) clears the result file.")


if __name__ == "__main__":
    main()
