"""Check a left/right pair of image-mode records (cpapp-b.bin, 3000 bytes each) against the rules that every stock pair obeys.

Why. Every design that widened the first-stage scaler (Lrc) picture came from build/build_fhpost.py and failed on the camera (F793, F795, F799,
F803). Read against the stock records of eight builds, those designs break relations between the rectangles, the Lrc start positions and the
history picture that hold in every stock pair, while the two designs that run (ogsq_v3, ogh2560_v1) break none (2026-11-20). This script is
those relations as code, so that a record pair is checked before a camera library is built from it.

The scale rule is the firmware's own one-axis fit 0x6f423e (start, size, output, pad multiple), ported to Python here and checked in the self-test
against the step, start position and pad stored in every stock record:
    step  = round(size / output)                       (Q12)
    first = start + (size - 4095/4096) / 2 - (step * (output // 2) - step / 2)      position of output sample 0 of the unpadded picture
    pad   = whole output samples that fit in `first`, rounded down to the pad multiple (2)
    phase = first - step * pad                         the Lrc start position; the padded output is the picture plus `pad` on each side

Columns, for a pair (W final width, seam = left final width, pad = left Dev rectangle x, ovl = left Lrc output - seam - pad):
  C1  horizontal step = fit(crop x, read-out width of both halves, W).step
  C2  left start position = that fit's phase
  C3  pad = that fit's pad
  C4  padded total (right Lrc output x + width) = W + 2 * pad
  C5  right start position = left start + right output x * step - right source x * 4096 (one sampling grid for both halves)
  C6  right start position is 4.0 to 8.0 source pixels
  C7  left half keeps 4.0 to 8.0 source pixels after its last sample
  C8  seam is a multiple of 32
  C9  ovl is 20 when pad is a multiple of 4, else 22; right output x = seam + pad - ovl
  C10 +0x18c = (max(ovl - pad, 0), 0) left and (0, max(ovl - pad, 0)) right
  C11 Dev rectangle: left (pad, row pad, output - pad, rows), right (output x, row pad, output - pad, rows)
  C12 the three final rectangles: left (0, 0, seam, rows), right (seam, 0, W - seam, rows)
  H1  history line size +0x1ac = content +0x1b4 rounded up to 8, each half
  H2  right history x = left history line size
  H3  content: left seam / 4, right (W - seam) / 4 rounded up
  H4  previous-history reads: left widths = left line + 16, + 12, + 6; right x = left line - 16, - 12, - 6;
      right widths = right line + 16, right content + 12, right content + 6 (so the first read ends at the end of the merged line)
  U1  level-2 read window: left width and right x are multiples of 8
  U1a the same, multiples of 64: holds in every pair of the A7 IV, FX2, FX30, A7S III, FX3 and FX6 (33 of 33), not in the Burano and one
      A1 pair, so it is counted over those six builds only and still required of a design (an A7 IV record)
  U2  the right half's Nrs window starts at least 32 after its read window
Rows, for every record with Lrc on:
  R1  vertical step = fit(crop y, crop rows, final rows).step      R2  vertical start position = its phase
  R3  row pad (Dev rectangle y) = its pad                         R4  Lrc output rows = final rows + 2 * row pad
  R5  first and last sample are equally far from the source's first and last row
  R6  the six quarter rectangles are final rows // 4 high

  python build/lint_split_record.py --selftest          stock pairs of eight builds and our designs; writes evidence/pipeline/split_record_lint.json
  python build/lint_split_record.py <design> [...]      one or more designs in modding/designs; exit status 1 if any rule is broken
Standard library only. Nothing in any firmware file or design is changed.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZE = 3000
STOCK = {"L": 0xBF7638, "R": 0xBF81F0}
FAMILY_ONLY = {"U1a": ("a7iv_602", "fx2_101", "fx30_601", "a7s3_501", "fx3_702", "fx6_602")}      # rules counted over these builds only
WORKING = ("ogsq_v3", "ogh2560_v1")                       # run on the camera (F682, F712)
FAILED = ("ogw4640_v1", "ogw4640_v2", "ogw5760_v1")       # restart on the camera (F799, F803, F793/F795)
NOT_RUN_OLD = ("ogw5152_v1", "og57full_v1")               # same generator, never run


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def rect(b, o):
    return struct.unpack_from("<4H", b, o)


def fit(start, size, out, multiple=2):
    """Port of 0x6f423e(start << 12, size << 12, 0, 0, out, multiple, ...): (step, phase, leading pad)."""
    p1, p2 = start << 12, size << 12
    n = max(out, 2)
    t = ((p2 << 1) & 0xFFFFFFFF) // n + 1
    step = t >> 1
    half_span = ((t & 0x1FFFF) >> 1) * (n >> 1) - ((t & 0x1FFFF) >> 2)
    centre = p1 + ((p2 - 0xFFF) >> 1)
    if centre < half_span:
        step = (centre * 2) // (n - 1)
        half_span = ((step & 0xFFFF) * (n - 1)) >> 1
    step &= 0xFFFF
    if step == 0:
        step = 1
    first = centre - half_span
    pad = (first // step) // multiple * multiple
    return step, first - step * pad, pad


def lrc(rec):
    w = struct.unpack_from("<6I", rec, 0x778)
    return {"on": w[0] == 1, "in": (w[1] >> 16, w[1] & 0xFFFF), "out": (w[2] >> 16, w[2] & 0xFFFF), "step": (w[3] >> 16, w[3] & 0xFFFF),
            "start": struct.unpack_from("<2i", rec, 0x788)}


def lint_rows(rec):
    """Row rules for one record. Returns {rule: (ok, detail)}."""
    k = lrc(rec)
    rows, pad = u16(rec, 0x196), u16(rec, 0x186)
    step, phase, fpad = fit(u16(rec, 0x13A), u16(rec, 0x13E), rows, 2)
    last = (k["start"][1] + (k["out"][1] - 1) * k["step"][1]) / 4096
    end = k["in"][1] - 1 - last
    res = {
        "R1": (k["step"][1] == step, f"step {k['step'][1]}, fit {step}"),
        "R2": (k["start"][1] == phase, f"start {k['start'][1]}, fit {phase}"),
        "R3": (pad == fpad, f"row pad {pad}, fit {fpad}"),
        "R4": (k["out"][1] == rows + 2 * pad == u16(rec, 0x17A), f"Lrc rows {k['out'][1]}, final {rows} + 2 x {pad}"),
        "R5": (abs(k["start"][1] / 4096 - end) < 0.02, f"first sample {k['start'][1] / 4096:.2f} rows in, last {end:.2f} rows from the end"),
        "R6": (all(u16(rec, o + 6) == rows // 4 for o in range(0x1A8, 0x1D8, 8)), f"quarter rows {[u16(rec, o + 6) for o in range(0x1A8, 0x1D8, 8)]}, final // 4 = {rows // 4}"),
    }
    return res


def lint_pair(L, R):
    """Column and history rules for a left/right pair. Returns ({rule: (ok, detail)}, facts)."""
    kl, kr = lrc(L), lrc(R)
    seam, rows = u16(L, 0x194), u16(L, 0x196)
    W = seam + u16(R, 0x194)
    pad, padv = u16(L, 0x184), u16(L, 0x186)
    lw, rx, rw = u16(L, 0x178), u16(R, 0x174), u16(R, 0x178)
    padded = rx + rw
    ovl = lw - seam - pad
    step, phase, fpad = fit(u16(L, 0x138), u16(L, 0x98) + u16(R, 0x98), W, 2)
    sh = kl["step"][0]
    last_l = (kl["start"][0] + (kl["out"][0] - 1) * sh) / 4096
    margin_l = kl["in"][0] - 1 - last_l
    start_r = kr["start"][0] / 4096
    lp, rp = u16(L, 0x1AC), u16(R, 0x1AC)
    lc, rc = u16(L, 0x1B4), u16(R, 0x1B4)
    x18 = max(ovl - pad, 0)
    res = {
        "C1": (sh == kr["step"][0] == step, f"step {sh}/{kr['step'][0]}, fit {step}"),
        "C2": (kl["start"][0] == phase, f"left start {kl['start'][0]}, fit {phase}"),
        "C3": (pad == fpad, f"pad {pad}, fit {fpad}"),
        "C4": (padded == W + 2 * pad, f"padded total {padded}, W + 2 x pad = {W + 2 * pad}"),
        "C5": (kr["start"][0] == kl["start"][0] + rx * sh - u16(R, 0x164) * 4096, f"right start {kr['start'][0]}, grid gives {kl['start'][0] + rx * sh - u16(R, 0x164) * 4096}"),
        "C6": (4.0 <= start_r < 8.0, f"right start {start_r:.2f} px"),
        "C7": (4.0 <= margin_l < 8.0, f"left margin after the last sample {margin_l:.2f} px"),
        "C8": (seam % 32 == 0, f"seam {seam}"),
        "C9": (ovl == (20 if pad % 4 == 0 else 22) and rx == seam + pad - ovl, f"overlap {ovl} with pad {pad}; right output x {rx}, seam + pad - ovl = {seam + pad - ovl}"),
        "C10": (struct.unpack_from("<2H", L, 0x18C) == (x18, 0) and struct.unpack_from("<2H", R, 0x18C) == (0, x18),
                f"+0x18c {struct.unpack_from('<2H', L, 0x18C)} / {struct.unpack_from('<2H', R, 0x18C)}, rule {x18}"),
        "C11": (rect(L, 0x184) == (pad, padv, lw - pad, rows) and rect(R, 0x184) == (rx, padv, rw - pad, rows), f"Dev rectangles {rect(L, 0x184)} / {rect(R, 0x184)}"),
        "C12": (all(rect(L, o) == (0, 0, seam, rows) and rect(R, o) == (seam, 0, W - seam, rows) for o in (0x190, 0x198, 0x1A0)), f"final {rect(L, 0x190)} / {rect(R, 0x190)}"),
        "H1": (lp == (lc + 7) // 8 * 8 and rp == (rc + 7) // 8 * 8, f"history line {lp}/{rp}, content {lc}/{rc}"),
        "H2": (u16(R, 0x1A8) == lp, f"right history x {u16(R, 0x1A8)}, left line {lp}"),
        "H3": (lc == seam // 4 and rc == (W - seam + 3) // 4, f"content {lc}/{rc}, seam / 4 = {seam // 4}, right {(W - seam + 3) // 4}"),
        "H4": ([u16(L, o) for o in (0x1C4, 0x1CC, 0x1D4)] == [lp + 16, lp + 12, lp + 6] and [u16(R, o) for o in (0x1C0, 0x1C8, 0x1D0)] == [lp - 16, lp - 12, lp - 6]
               and [u16(R, o) for o in (0x1C4, 0x1CC, 0x1D4)] == [rp + 16, rc + 12, rc + 6],
               f"previous reads left w {[u16(L, o) for o in (0x1C4, 0x1CC, 0x1D4)]}, right x {[u16(R, o) for o in (0x1C0, 0x1C8, 0x1D0)]} w {[u16(R, o) for o in (0x1C4, 0x1CC, 0x1D4)]}; "
               f"first right read ends at {u16(R, 0x1C0) + u16(R, 0x1C4)}, merged line {lp + rp}"),
        "U1": (u16(L, 0x12C) % 8 == 0 and u16(R, 0x128) % 8 == 0, f"read window left width {u16(L, 0x12C)}, right x {u16(R, 0x128)}"),
        "U1a": (u16(L, 0x12C) % 64 == 0 and u16(R, 0x128) % 64 == 0, f"read window left width {u16(L, 0x12C)}, right x {u16(R, 0x128)}"),
        "U2": (u16(R, 0x144) - u16(R, 0x128) >= 32, f"right Nrs window starts {u16(R, 0x144) - u16(R, 0x128)} after its read window"),
    }
    facts = {"W": W, "rows": rows, "seam": seam, "pad": pad, "row_pad": padv, "overlap": ovl, "padded_total": padded, "lrc_out": [lw, rw], "step_h": sh,
             "start_px": [round(kl["start"][0] / 4096, 2), round(start_r, 2)], "left_margin_px": round(margin_l, 2),
             "source_windows": [[u16(L, 0x164), u16(L, 0x168)], [u16(R, 0x164), u16(R, 0x168)]], "history_line": [lp, rp]}
    return res, facts


def lint_design_records(L, R):
    res, facts = lint_pair(L, R)
    for h, rec in (("L", L), ("R", R)):
        for rule, v in lint_rows(rec).items():
            ok, detail = res.get(rule, (True, ""))
            res[rule] = (ok and v[0], (detail + "; " if detail else "") + f"{h}: {v[1]}")
    return res, facts


def load_design(name):
    d = json.loads((ROOT / f"modding/designs/{name}.json").read_text(encoding="utf8"))
    recs = {("L" if p["addr"] == hex(STOCK["L"]) else "R"): bytes.fromhex(p["new"]) for p in d["patches"] if p["kind"] == "R"}
    assert set(recs) == {"L", "R"} and all(len(r) == SIZE for r in recs.values()), name
    return recs


def stock_records():
    """Every Lrc word group found by build/scan_lrc_records.py in the eight builds: (build, file offset of the record, record)."""
    inv = json.loads((ROOT / "evidence/pipeline/lrc_records_other_cameras.json").read_text(encoding="utf8"))["builds"]
    for build, v in inv.items():
        img = (ROOT / v["image"]).read_bytes()
        for off in v["offsets"]:
            o = int(off, 16) - 0x778
            yield build, o, img[o:o + SIZE]


def stock_pairs():
    prev = None
    for build, o, rec in stock_records():
        if prev and prev[0] == build and prev[1] + SIZE == o and u16(prev[2], 0x190) == 0 and u16(rec, 0x190) != 0 and u16(prev[2], 0x164) == 0 and u16(rec, 0x164) != 0:
            yield build, prev[1], prev[2], rec
        prev = (build, o, rec)


def selftest():
    out = {"about": "Rules that every stock left/right record pair obeys, counted over the stock records of eight builds, and what our designs break. "
                    "Generated by build/lint_split_record.py --selftest; see its header for the rules.", "stock": {}, "designs": {}}
    counts, fails, npairs, of = {}, {}, 0, {}
    for build, o, L, R in stock_pairs():
        npairs += 1
        res, facts = lint_pair(L, R)
        for rule, (ok, detail) in res.items():
            if rule in FAMILY_ONLY and build not in FAMILY_ONLY[rule]:
                continue
            of[rule] = of.get(rule, 0) + 1
            counts[rule] = counts.get(rule, 0) + ok
            if not ok:
                fails.setdefault(rule, []).append({"build": build, "left_record_file_offset": hex(o), "detail": detail})
    rcounts, rfails, nrec = {}, {}, 0
    for build, o, rec in stock_records():
        if not lrc(rec)["on"]:
            continue
        nrec += 1
        for rule, (ok, detail) in lint_rows(rec).items():
            rcounts[rule] = rcounts.get(rule, 0) + ok
            if not ok:
                rfails.setdefault(rule, []).append({"build": build, "record_file_offset": hex(o), "detail": detail})
    out["stock"] = {"pairs": npairs, "records": nrec, "pair_rules_holding": {r: f"{c} of {of[r]}" for r, c in counts.items()}, "row_rules_holding": rcounts,
                    "rules_counted_over_some_builds_only": {r: list(v) for r, v in FAMILY_ONLY.items()},
                    "pair_rule_exceptions": fails, "row_rule_exceptions": rfails}
    print(f"stock pairs {npairs}:", " ".join(f"{r} {c}/{of[r]}" for r, c in counts.items()))
    print(f"stock records {nrec}:", " ".join(f"{r} {c}" for r, c in rcounts.items()))
    for rule, fl in {**fails, **rfails}.items():
        print("  exceptions", rule, len(fl), fl[:3])
    ok_all = all(c == of[r] for r, c in counts.items()) and all(c == nrec for c in rcounts.values())
    names = list(WORKING) + list(FAILED) + list(NOT_RUN_OLD) + [a for a in sys.argv[2:]]
    for name in names:
        if not (ROOT / f"modding/designs/{name}.json").exists():
            continue
        recs = load_design(name)
        res, facts = lint_design_records(recs["L"], recs["R"])
        broken = {r: d for r, (ok, d) in res.items() if not ok}
        out["designs"][name] = {"camera": "runs" if name in WORKING else "restart" if name in FAILED else "not run", "facts": facts, "broken": broken}
        print(f"{name:14s} {out['designs'][name]['camera']:8s} broken: {sorted(broken) or 'none'}")
    assert all(not out["designs"][n]["broken"] for n in WORKING), "a design that runs on the camera breaks a rule: the rule is wrong"
    assert all(out["designs"][n]["broken"] for n in FAILED + NOT_RUN_OLD if n in out["designs"])
    out["every_rule_holds_on_every_stock_pair"] = ok_all
    (ROOT / "evidence/pipeline/split_record_lint.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    return ok_all


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        ok = selftest()
        print("every rule holds on every stock pair:", ok)
        sys.exit(0 if ok else 2)
    bad = False
    for name in sys.argv[1:]:
        recs = load_design(name)
        res, facts = lint_design_records(recs["L"], recs["R"])
        broken = {r: d for r, (ok, d) in res.items() if not ok}
        print(name, json.dumps(facts))
        for r, d in broken.items():
            print("   BROKEN", r, d)
        print("   clean" if not broken else f"   {len(broken)} rules broken")
        bad = bad or bool(broken)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
