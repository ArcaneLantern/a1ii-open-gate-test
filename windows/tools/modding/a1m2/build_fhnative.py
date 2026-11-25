"""Build a full-height design whose first-stage scaler (Lrc) gives a picture of any size W x H, with the column geometry the firmware's own
split planner computes (cpapp-b.bin, A7 IV 6.02). Design only: nothing is written to a firmware file and nothing is sent to a camera.

Why. build/build_fhpost.py kept the stock source windows and a fixed padding (6 columns, 22 of seam overlap, rows + 8) for every width. Every
design it made wider than stock restarted the camera (F793, F795, F799, F803), and each breaks rules that hold in all 85 stock left/right
pairs of eight builds (build/lint_split_record.py; finding F900). No rule-clean wide record had been tried.

How a record pair is made, on the working baseline ogsq_v3 (full-height first stage 7032 x 4688, crop 7008 x 4672 at 12, 8):
  columns   the firmware's split-zoom parameter builder 0x6ee16e (geometry 0x6f1222 inside it), run in Unicorn with the argument staging
            worked out in "Astra Analysis Check/geometry_replay.py" (the owner's outside check, 2026-11-19). It writes record +0x128 to +0x1d7:
            the level-2 read windows, the Nrs/Sig/Lrc source windows, the padded Lrc outputs, the Dev and final rectangles, +0x18c, and the six
            quarter (history) rectangles. Its history rectangles are fed back until they no longer change.
  rows      the movie records' rule, not the split-zoom one (which pads rows differently: 2442 where stock has 2446): row pad from the
            firmware's one-axis fit (lint_split_record.fit, a port of 0x6f423e checked on 216 stock records), padded rows = rows + 2 x pad,
            Dev rectangle y = pad. Row pad is 4 at 2438 and 2560 rows and 6 at 3840.
  four movie-record fields the split-zoom path leaves at its own values (each rule holds on every stock A7 IV and FX30 pair, self-test):
            left  +0x138 = crop x, +0x13c = read window width - crop x;  right +0x134 = frame width - read window x,
            right +0x13c = crop end - read window x
  outside the planner's range (rules checked on the stock pairs in the self-test):
            Dcv +0x64e = +0x64a + read window width / 2 - 1, copied to +0x9fe, +0xa9e, +0xb3e
            left Sig seam, +0x768 low half = right source x / 2 (gen_block_words.inputs reads it back as a packer input)
            +0x906, +0x914, +0x934 low half (inputs of the second Dev packer): the planner's own packed words
  words     Arc, Nrs, Sig, Lrc and both Dev packers by the firmware's packers (build_fhpost.finish), second Dev copy mirrored as stock does

Self-test (--selftest; writes evidence/pipeline/fhnative_selftest.json):
  1. 4336 x 2438 gives ogsq_v3's records and 4336 x 2560 gives ogh2560_v1's, byte for byte (both run on the camera: F682, F712)
  2. each stock A7 IV pair and each stock FX30 pair is rebuilt from its own frame, crop and output size and compared with the stored record
     over every field this generator writes (FX30: the A7 IV's code on the FX30's geometry; its 4624 pair has the 2,364-wide half)
  3. the designs made here pass build/lint_split_record.py, and their column words equal the planner's own packed words

  C:\\Python313\\python.exe -B build/build_fhnative.py --selftest
  C:\\Python313\\python.exe -B build/build_fhnative.py <name> <W> <H> [--register]
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import gen_block_words as G  # noqa: E402
import build_fhstage as F  # noqa: E402
import build_fhpost as P  # noqa: E402
import build_og4k_data as O  # noqa: E402
import lint_split_record as LINT  # noqa: E402
from og57_axis_geometry import arm_call  # noqa: E402

BASE, SIZE, STOCK = F.BASE, F.SIZE, F.STOCK
PLANNER = 0x6EE16E
IMAGE_SHA256 = "7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b"
COLS = (0x128, 0x1D8)                                   # what the planner writes
DCV_COPIES = (0x9FE, 0xA9E, 0xB3E)
SETTINGS = ((0x906, 0x904, 16), (0x914, 0x914, 0), (0x934, 0x934, 0))      # (record u16, word holding it, shift)


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def put16(b, o, v):
    struct.pack_into("<H", b, o, v)


def pair_inputs(rec):
    """Frame, crop and output size of a left/right pair, read from its records (as geometry_replay.crosscheck_records)."""
    L, R = rec["L"], rec["R"]
    frame = (u16(R, 0x164) + u16(R, 0x168), u16(L, 0x77C))
    crop = (u16(L, 0x138), u16(L, 0x13A), u16(L, 0x98) + u16(R, 0x98), u16(L, 0x13E))
    target = (u16(L, 0x194) + u16(R, 0x194), u16(L, 0x196))
    return frame, crop, target


def planner(M, mode_bytes, target, previous, frame, crop):
    """One call of 0x6ee16e. Returns the two geometry buffers and the two packed-word buffers (3000 bytes each, record layout / block layout)."""
    uc = M.m.uc
    w, h = target
    args = [G.SCR + 0x2000 + i * 0x1000 for i in range(12)]
    uc.mem_write(args[0], bytes(0xC000))
    uc.mem_write(args[0], struct.pack("<12H", 0, 0, *frame, 0, 0, *frame, *crop))
    x, y, cw, ch = crop
    uc.mem_write(args[1], struct.pack("<8I", x, 0, y, 0, cw, 0, ch, 0))
    uc.mem_write(args[2], mode_bytes)                                        # 36 bytes of mode data the caller copies from the record
    uc.mem_write(args[3], struct.pack("<IHHffHH", 0, 4, 4, 1., 1., w, h))    # zoom state 0, grouping 4/4, unity zoom
    uc.mem_write(args[4], struct.pack("<HH", w, h))
    for index, side in enumerate(("L", "R"), 5):
        uc.mem_write(args[index], previous[side])
    for index in (8, 10):
        uc.mem_write(args[index], bytes([0xA5]) * SIZE)
    status = arm_call(M.m, PLANNER, *args)
    assert status == 0, ("planner refused", target, status)
    geo = {s: bytes(uc.mem_read(args[i], SIZE)) for s, i in (("L", 7), ("R", 9))}
    packed = {s: bytes(uc.mem_read(args[i], SIZE)) for s, i in (("L", 8), ("R", 10))}
    return geo, packed


def native_columns(M, base, target, frame, crop):
    """The planner's result in the steady state: its history rectangles fed back until they stop changing."""
    prev = {s: base[s][0x1A8:0x1C0] for s in "LR"}
    for _ in range(6):
        geo, packed = planner(M, base["L"][0x250:0x274], target, prev, frame, crop)
        now = {s: geo[s][0x1A8:0x1C0] for s in "LR"}
        if now == prev:
            return geo, packed
        prev = now
    raise AssertionError("history rectangles do not settle")


def word_table(M, writer):
    """(record offset, packed-buffer offset) of every word of one block's register lists."""
    w = M.sg[writer]
    return [(po + 4 * n, oo - 0xC + 4 * n) for po, oo, lst in zip([int(x, 16) for x in w["source_offsets_in_shared_structure"]],
                                                                [int(x, 16) for x in w["source_offsets_in_own_structure"]], w["lists"])
            for n in range(len(lst["register_offsets"]))]


def assemble(M, base, target, frame=None, crop=None, mirror_as=None):
    """Records for an Lrc picture `target` on `base` (a working left/right pair). Returns (records, facts)."""
    f0, c0, _ = pair_inputs(base)
    frame, crop = frame or f0, crop or c0
    W, H = target
    geo, packed = native_columns(M, base, target, frame, crop)
    _, _, padv = LINT.fit(crop[1], crop[3], H, 2)
    dev = dict(word_table(M, "writeCamDevSgcTable"))
    rec = {}
    for s in "LR":
        r = bytearray(base[s])
        r[COLS[0]:COLS[1]] = geo[s][COLS[0]:COLS[1]]
        # rows by the movie rule
        assert u16(r, 0x196) == H and u16(r, 0x18A) == H
        for o in (0x17A, 0x182):
            put16(r, o, H + 2 * padv)
        put16(r, 0x186, padv)
        # the movie records' read-window fields
        if s == "L":
            put16(r, 0x138, crop[0])
            put16(r, 0x13C, u16(r, 0x12C) - crop[0])
        else:
            put16(r, 0x134, frame[0] - u16(r, 0x128))
            put16(r, 0x13C, crop[0] + crop[2] - u16(r, 0x128))
        # Dcv: the end of the read window in pixel pairs (the word is 0 in a mode that has Dcv off, e.g. the FX30's pair at 0xb76648)
        if u16(base[s], 0x64E):
            put16(r, 0x64E, u16(r, 0x64A) + u16(r, 0x12C) // 2 - 1)
            for o in DCV_COPIES:
                put16(r, o, u16(r, 0x64E))
        # inputs of the second Dev packer that the record stores: the planner's own
        for field, word, shift in SETTINGS:
            put16(r, field, (u32(packed[s], dev[word]) >> shift) & 0xFFFF)
        rec[s] = r
    # left Sig seam (low half of Sig word 0xbb0): the right half's source x in pixel pairs
    put16(rec["L"], 0x768, u16(rec["R"], 0x164) // 2)
    done, words, disagree = P.finish(M, rec, mirror_as or M.stock, strict=False)
    facts = {"row_pad": padv, "planner_packed": packed, "planner_geometry": geo, "fitted_dev_rules_that_disagree": disagree or None}
    return done, facts


def column_word_check(M, rec, packed):
    """Our finished words against the planner's own packed words. Rows are padded differently on the split-zoom path, so a word may differ in a
    half that holds a row value; returns the words that differ, per half, as (offset, ours, planner's)."""
    out = {}
    for s in "LR":
        diff = []
        for writer in ("writeCamNrsSgcTable", "writeCamSigSgcTable", "writeCamLrcSgcTable", "writeCamDevSgcTable"):
            for po, oo in word_table(M, writer):
                a, b = u32(rec[s], po), u32(packed[s], oo)
                if b == 0xA5A5A5A5 or a == b:
                    continue
                diff.append({"offset": hex(po), "ours": hex(a), "planner": hex(b), "high_half_differs": a >> 16 != b >> 16, "low_half_differs": a & 0xFFFF != b & 0xFFFF})
        out[s] = diff
    return out


def changed(a, b):
    return [o for o in range(0, SIZE, 2) if a[o:o + 2] != b[o:o + 2]]


def stock_pairs_of(build):
    """Stock split pairs of one build as (file offset of the left record, {"L":, "R":})."""
    for b, o, L, R in LINT.stock_pairs():
        if b == build:
            yield o, {"L": L, "R": R}


def selftest(M):
    res = {"about": "Self-test of build/build_fhnative.py; see its header.", "image_sha256": IMAGE_SHA256}
    _, sq3 = F.load("ogsq_v3")
    _, h2560 = F.load("ogh2560_v1")
    # 1. the two designs that run on the camera
    for name, want, target in (("ogsq_v3", sq3, (4336, 2438)), ("ogh2560_v1", h2560, (4336, 2560))):
        got, _ = assemble(M, sq3, target)
        diff = {s: [hex(o) for o in changed(got[s], want[s])] for s in "LR"}
        res[f"reproduces_{name}"] = not any(diff.values())
        print(f"reproduces {name}: {res[f'reproduces_{name}']}", {s: d[:12] for s, d in diff.items() if d})
    # 2. stock pairs rebuilt from their own geometry
    rows = []
    for build in ("a7iv_602", "fx30_601"):
        for off, pair in stock_pairs_of(build):
            frame, crop, target = pair_inputs(pair)
            got, facts = assemble(M, pair, target, mirror_as=pair)
            diff = {s: changed(got[s], pair[s]) for s in "LR"}
            lint, lf = LINT.lint_design_records(got["L"], got["R"])
            rows.append({"build": build, "left_record_file_offset": hex(off), "frame": frame, "crop": crop, "output": target, "lrc_out": lf["lrc_out"],
                         "fields_that_differ_from_the_stored_record": {s: [{"offset": hex(o), "stored": u16(pair[s], o), "rebuilt": u16(got[s], o)} for o in d] for s, d in diff.items()},
                         "lint_broken": sorted(r for r, (ok, _) in lint.items() if not ok)})
            print(f"{build} {hex(off)} out {target} halves {lf['lrc_out']}: differs L {len(diff['L'])} R {len(diff['R'])}",
                  {s: [(hex(o), u16(pair[s], o), u16(got[s], o)) for o in d[:8]] for s, d in diff.items() if d})
    res["stock_pairs_rebuilt"] = rows
    # 3. cross-mode: the FX30's 4624-wide pair (2,364-wide half) built from its 4336-wide pair. The two modes share the sensor read-out and
    #    differ in stage rows (3356 / 3148), which this generator does not touch, so fields that follow the stage rows stay the base's.
    fx = dict(stock_pairs_of("fx30_601"))
    base, want = fx[0xB71440], fx[0xB6E560]
    frame, crop, target = pair_inputs(want)
    got, _ = assemble(M, base, target, frame=frame, crop=crop, mirror_as=base)
    dr = pair_inputs(base)[0][1] - frame[1]
    cross = {}
    for h in "LR":
        d = changed(got[h], want[h])
        rowlike = lambda o: u16(base[h], o) - u16(want[h], o) in (dr, dr // 2, dr // 4, 4)
        cross[h] = {"fields_that_differ_from_the_real_record": len(d), "inside_the_planner_range": [hex(o) for o in d if COLS[0] <= o < COLS[1]],
                    "not_following_the_stage_rows": [{"offset": hex(o), "base": u16(base[h], o), "real": u16(want[h], o)} for o in d if not rowlike(o)]}
    res["fx30_4624_pair_from_its_4336_pair"] = cross
    known = {"0x2a0", "0x300", "0x30c", "0x31c", "0x32e", "0x5ac", "0x95e"}      # sensor rows, a first-stage (Cas) word, the first active row
    res["cross_mode_ok"] = all(not c["inside_the_planner_range"] and {f["offset"] for f in c["not_following_the_stage_rows"]} <= known for c in cross.values())
    print("FX30 4624 pair from its 4336 pair:", {h: (c["fields_that_differ_from_the_real_record"], [f["offset"] for f in c["not_following_the_stage_rows"]]) for h, c in cross.items()},
          "ok" if res["cross_mode_ok"] else "NOT OK")
    res["a7iv_pairs_exact"] = all(not any(r["fields_that_differ_from_the_stored_record"].values()) for r in rows if r["build"] == "a7iv_602")
    res["fx30_pairs_exact"] = sum(not any(r["fields_that_differ_from_the_stored_record"].values()) for r in rows if r["build"] == "fx30_601")
    (ROOT / "evidence/pipeline/fhnative_selftest.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf8", newline="\n")
    return res


def main():
    img = next(p for p in (ROOT / "work/extracted/a7iv_602").rglob("cpapp-b.bin") if "nflasha8" in p.as_posix()).read_bytes()
    sha = hashlib.sha256(img).hexdigest()
    assert sha == IMAGE_SHA256
    M = F.Model(img)
    if sys.argv[1] == "--selftest":
        res = selftest(M)
        ok = res["reproduces_ogsq_v3"] and res["reproduces_ogh2560_v1"] and res["a7iv_pairs_exact"] and res["fx30_pairs_exact"] == 5 and res["cross_mode_ok"]
        print("self-test:", "passed" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    name, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    sq3_design, sq3 = F.load("ogsq_v3")
    assert sq3_design["artifact_sha256"] == sha
    ctl, cf = assemble(M, sq3, (4336, 2438))
    assert all(ctl[h] == sq3[h] for h in "LR"), "ogsq_v3 not reproduced"
    key = lambda w: (w["offset"], w["high_half_differs"], w["low_half_differs"])
    baseline_words = {h: {key(w) for w in ws} for h, ws in column_word_check(M, ctl, cf["planner_packed"]).items()}
    rec, facts = assemble(M, sq3, (W, H))
    lint, lf = LINT.lint_design_records(rec["L"], rec["R"])
    broken = {r: d for r, (ok, d) in lint.items() if not ok}
    assert not broken, broken
    words = column_word_check(M, rec, facts["planner_packed"])
    # ogsq_v3 (runs on the camera) differs from the planner's own packed words only where a half-word holds a row value (the split-zoom path
    # pads rows differently). A design may differ in those same half-words and nowhere else: its column words are the planner's.
    column_halves = {s: [w for w in ws if key(w) not in baseline_words[s]] for s, ws in words.items()}
    assert not any(column_halves.values()), column_halves
    stock = M.stock
    lrc = {}
    for h in "LR":
        k = LINT.lrc(rec[h])
        lrc[h] = {"input": list(k["in"]), "output": list(k["out"]), "step_q12": list(k["step"]), "start_h": k["start"][0], "start_v": k["start"][1],
                  "start_h_px": round(k["start"][0] / 4096, 3), "source_window": [u16(rec[h], 0x164), u16(rec[h], 0x168)],
                  "read_window": [u16(rec[h], 0x128), u16(rec[h], 0x12C)]}
    rc_in = [u16(rec["R"], 0x190) + u16(rec["R"], 0x1A4) - u16(rec["L"], 0x1A0), u16(rec["R"], 0x1A6)]
    assert rc_in == [W, H], rc_in
    changed_fields = {h: [hex(o) for o in changed(rec[h], sq3[h])] for h in "LR"}
    patches = [p for p in sq3_design["patches"] if p["kind"] == "S"]
    for h in "LR":
        n = sum(rec[h][x:x + 2] != stock[h][x:x + 2] for x in range(0, SIZE, 2))
        patches.append({"kind": "R", "addr": hex(STOCK[h]), "old": stock[h].hex(), "new": rec[h].hex(),
                        "note": f"0x8c0 {'left' if h == 'L' else 'right'} record: ogsq_v3's full-height first stage, Lrc picture {W}x{H} with the firmware "
                                f"planner's column geometry (seam at {lf['seam']}, pad {lf['pad']}); {n} fields differ from stock", "where": "file"})
    assert len(patches) == 13 and sum(len(p["new"]) // 2 for p in patches) == 6024
    out = {"design": name, "title": f"Full-height frame (ogsq_v3), first-stage scaler picture {W}x{H} instead of 4336x2438, column geometry from the firmware's split planner",
           "artifact": "cpapp-b.bin", "artifact_sha256": sha, "generated_by": f"build/build_fhnative.py {name} {W} {H}",
           "summary": {"sites": 13, "bytes": 6024, "stage_height": 4688, "front_end": [W, H], "final_columns": [lf["seam"], W - lf["seam"]],
                       "column_pad": lf["pad"], "row_pad": lf["row_pad"], "seam_overlap": lf["overlap"], "padded_total": lf["padded_total"],
                       "lrc_output_per_half": {h: lrc[h]["output"] for h in "LR"}, "lrc_step_q12": {h: lrc[h]["step_q12"] for h in "LR"},
                       "lrc_start_px": lf["start_px"], "left_margin_after_last_sample_px": lf["left_margin_px"], "source_windows": lf["source_windows"],
                       "read_windows": {h: lrc[h]["read_window"] for h in "LR"}, "history_line": lf["history_line"],
                       "fields_changed_against_ogsq_v3": {h: len(v) for h, v in changed_fields.items()},
                       "plus": "26 bytes of the stored drive-parameter record, as ogsq_v3 (vertical sampling ratio 27/32)",
                       "expected_working_state": {"readout": [7032, 4688], "crop": [7008, 4672], "front_end": [W, H]}},
           "self_checks": ["ogsq_v3's records reproduced exactly for 4336x2438", "build/lint_split_record.py: no rule broken (rules that hold on all 85 stock pairs)",
                           "Nrs, Sig, Lrc and Dev words equal the firmware planner's own packed words except in the half-words where ogsq_v3 "
                           "(which runs on the camera) also differs from it: the row values, padded by the movie rule"],
           "words_that_differ_from_the_planner": words,
           "dev_parameter_words_where_the_fitted_rules_disagree": facts["fitted_dev_rules_that_disagree"],
           "lrc": lrc, "changed_fields_against_ogsq_v3": changed_fields, "patches": patches, "stored_record_extra": sq3_design["stored_record_extra"]}
    d = ROOT / "modding" / "designs"
    (d / f"{name}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    (d / f"{name}_pokes_file.txt").write_text("".join(f"{p['addr']} {p['new']}\n" for p in patches), encoding="utf8", newline="\n")
    src = ROOT / "evidence/pipeline/ogsq_v3_drvparam_records_emu.json"
    rj = json.loads(src.read_text(encoding="utf8"))
    rj["about"] = (f"Stored drive-parameter record of mode 0x8c0 for {name}: ogsq_v3's (the record depends on the sensor cells, which are the same; the "
                   "vertical sampling ratio 27/32 counts the 7008x4672 stage window as 16:9). Copied by build/build_fhnative.py")
    (ROOT / "evidence/pipeline" / f"{name}_drvparam_records_emu.json").write_text(json.dumps(rj, indent=1) + "\n", encoding="utf8", newline="\n")
    print(json.dumps(out["summary"]))
    print("changed against ogsq_v3:", {h: len(v) for h, v in changed_fields.items()}, "| words differing from the planner beyond the baseline's row half-words: none")
    if "--register" in sys.argv:
        import records
        st = records.Store()
        st.begin(f"design {name}: first-stage scaler picture {W}x{H} with the firmware planner's column geometry, as patch sites",
                 "the owner asked for real 5.7K detail (2026-11-20): the earlier width designs broke stock record rules (F900)",
                 evidence=f"modding/designs/{name}.json from build/build_fhnative.py", author="build_fhnative.py")
        for i, p in enumerate(patches, 1):
            a = int(p["addr"], 16)
            data = {"design": name, "design_title": out["title"], "artifact": "cpapp-b.bin", "artifact_sha256": sha, "addr": p["addr"],
                    "file_off": hex(a - BASE), "length": len(p["new"]) // 2, "old_hex": p["old"], "new_hex": p["new"], "patch_kind": p["kind"],
                    "risk_class": "R2 as a file change; tested only in memory (RM, by the owner's go-ahead per run)", "old_verified": True,
                    "note": p["note"], "where": "file", "source": f"modding/designs/{name}.json"}
            rid = f"PS-{name}-{i}"
            ttl = f"{name} {p['kind']}: {p['note']}"
            if rid in st.records:
                st.amend(rid, data, title=ttl)
            else:
                st.add("patch_site", ttl, data, id=rid, level="static", certainty="inferred", build="a7iv_602", subsystem="patch-design")
        print("registered:", st.commit(), "changes")


if __name__ == "__main__":
    main()
