"""A1 II 4.00 (a1m2_400) open gate, sensor and first-stage side: design ogsq_a1m2_v1 (A1 II port, 2026-11-26).

  C:\\Python313\\python.exe -B build\\build_og_a1m2.py [--check]       (needs Unicorn and capstone: C:\\Python313 has them)

writes modding/designs/ogsq_a1m2_v1.json and evidence/a1m2/sensor/*.json. Nothing is written to a firmware file or sent to a camera.

What the A1 II does in FF 4K (read from cpapp-b.bin 4.00, every fact asserted below; modding/A1M2_PORT.md section 2):
  - 44 drive modes (ids 0xe9eb40). 0x820, 0x2820, 0x8c0, 0x28c0 (indices 2..5) read the sensor 2x2-binned, 4320 x 2430 (+ margins) =
    a 16:9 band of 8640 x 4860 physical rows: their crop, stream-0, stream-1 (phase detect), LC rows are equal, the read-out rows differ only
    in the frame-length field [18], and all four use register-matrix column 2 (sensor mode 0x14), which no other mode uses. 0x8c0/0x28c0 =
    23.98p (60 Hz table) / 25.00p (50 Hz), 0x820/0x2820 = 29.97p / 25.00p.
  - The record selector 0x279f20 gives 0x820 and 0x8c0 the pair 0xdf6844 / 0xdf73fc and 0x2820 and 0x28c0 the pair 0xe023c4 / 0xe02f7c
    (same rows, another split of the columns). The first scaler (Lrc) runs 1:1 (4320 x 2430); the second scaler makes 3840 x 2160.
  - The sensor's vertical window is set by two register-matrix rows: shadow +0x20 (start block s) and +0x24 (half-height n, x2 in the 3x3
    and 6x6 modes): s + n = 31 in all 25 columns in use; full height is s = 1, n = 30 (the still modes), the 4K band s = 6, n = 25. In sensor
    mode 0x14 the register at shadow +0x90 is 33 + n in all three of its windows (58 / 56 / 50 at n = 25 / 23 / 17), and the read-out table's
    field [11] mirrors it. The A1 and A1 II matrices are identical.
So the open gate keeps the 4K mode's own sensor mode, binning and line timing and only makes the window full height: 4320 x 2880 (3:2).
The full-height read-out (about 2,912 sensor lines) fits every frame length these modes use (6,320 / 5,056 / 5,888 lines at 23.98 / 29.97 /
25p).

The cells (each of the four modes' rows; the full-height values are those of the still and live-view modes that read full height):
  matrix   column 2, rows +0x20 6 -> 1, +0x24 25 -> 30, +0x90 58 -> 63
  crop     0xe9ebf0 (20) [3] band row 222 -> 0, [9] first phase-detect block 5 -> 0
  stream-0 0xfa02aa (38) [13] window height 2430 -> 2880 (margins 12, 2, 8 / 8, 2 kept)
  stream-1 0xfa09ca (38) [13] phase-detect rows 114 -> 134 (134 in every full-height binned mode; the records' total +0x290 =
           [9] + [13] + [15], and the 2x2 family keeps [9] 113 and [15] 36)
  LC       0xfa10ea (14) [4] 535 -> 91 (= 91 + 2 x band row in 2x2), [6] 631 -> 151 (151 in every full-height mode)
  read-out 0xea0808 (44) [11] 58 -> 63 (mirror of +0x90), [20], [21] read-out length 679 -> 792 (rows / 4 + 63.5, as stock)
  geometry 0xe4b640 (12-byte rows by mode id) +10 band row 222 -> 0

The picture records: a row model fitted on the A1 II's own 2x2-binned pairs (4K 0xdf6844 2446 rows, 3840 crop 0xdf50d4 2168 rows, S35 FHD
0xe00c54 / 0xdfdd74 1632 rows): each field before the first scaler that follows the geometry does so as a rule in the stage rows H, the
phase-detect rows p, the window row and the band row; then the column geometry and every register word come from build/build_fhnative.assemble
(the firmware's split planner and packers, which rebuild every stock A1 II 4K, crop and S35 pair byte for byte). Self-test: the 4K pair is
rebuilt from the crop pair and the crop pair from the 4K pair. The Lrc squeezes 4320 x 2880 into the stock 4320 x 2430 front end; with the
vertical sampling ratio 27/16 over 2/1 (= 27/32) in each stored record the resize fit keeps every row (the A7 IV's ogsq_v3, F681/F682), and the
output-size step makes the file 3840 x 2560.
"""
import hashlib
import json
import struct
import sys
from fractions import Fraction as Fr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402
import build_fhstage as F  # noqa: E402
import build_fhnative as N  # noqa: E402
import lint_split_record as LINT  # noqa: E402
import emu_drvparam as E  # noqa: E402
import emu_record_selector as S  # noqa: E402

B, SIZE = 0x108000, F.SIZE
BUILD = "a1m2_400"
REAL = "--real-rows" in sys.argv                     # variant: the first scaler keeps every row (the A7 IV's ogh2560_v1 form)
BOTTOM = "--bottom-band" in sys.argv                  # diagnostic (the A7 IV's fhs3958b, F664/F665): full-height sensor frame and tables,
                                                      # stock-size first stage taken from the BOTTOM of the frame, everything after stock
NAME = "ogbb_a1m2_v1" if BOTTOM else "ogh2880_a1m2_v1" if REAL else "ogsq_a1m2_v1"
BOTTOM_ROWS = 450                                     # the stage starts 450 active rows down the 2,880-row frame (2880 - 2430)
X = locate_file.locate(BUILD, "cpapp-b.bin").read_bytes()
A = locate_file.locate("a7iv_602", "cpapp-b.bin").read_bytes()
SHA = hashlib.sha256(X).hexdigest()
IDS, NMODES = 0xE9EB40, 44
MODES = (0x820, 0x2820, 0x8C0, 0x28C0)
COLMAP, MATRIX, MROW, MCOL = 0x11EF2A0, 0x11EE600, 32, 2
GEO = 0xE4B640                                         # 12-byte rows: u32 mode id, u16 x3, u16 band row
CROP, S0, S1, LC, RO = (0xE9EBF0, 20), (0xFA02AA, 38), (0xFA09CA, 38), (0xFA10EA, 14), (0xEA0808, 44)
PAIRS = {"A": {"L": 0xDF6844, "R": 0xDF73FC}, "B": {"L": 0xE023C4, "R": 0xE02F7C}}
USES = {"A": (0x820, 0x8C0), "B": (0x2820, 0x28C0)}
# the 2x2-binned family the row model is fitted on: pair -> a mode that uses it (its table rows give the geometry)
FAMILY = {"A": ({"L": 0xDF6844, "R": 0xDF73FC}, 0x8C0), "crop": ({"L": 0xDF50D4, "R": 0xDF5C8C}, 0x7E0),
          "s35a": ({"L": 0xE00C54, "R": 0xE0180C}, 0xB21), "s35b": ({"L": 0xDFDD74, "R": 0xDFE92C}, 0xAE1)}
# other families: only for the rules in H and the window row (their phase-detect layout and constants differ)
OTHER = {"full-res S35": ({"L": 0xDF7FB4, "R": 0xDF8B6C}, 0x821), "3x3": ({"L": 0xDFF4E4, "R": 0xE0009C}, 0xB20)}
MATRIX_EDITS = {0x20: (6, 1), 0x24: (0x19, 0x1E), 0x90: (0x3A, 0x3F)}     # shadow offset: (stock, full height)
NEW_H = 2880
PAV = (2, 1) if (REAL or BOTTOM) else (27, 16)                     # stored record +6/+7 over +4/+5 = 2/1: 27/32 (real rows: stock 2/1)
STOCK_OUT = (4320, 2430)
OUT = (4320, 2880) if REAL else STOCK_OUT              # the first scaler's picture (the front end)

u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
rd = lambda a, n: X[a - B:a - B + n]


def row(tbl, i):
    base, n = tbl
    return list(struct.unpack_from("<%dH" % (n // 2), X, base - B + n * i))


def ids():
    return list(struct.unpack_from("<%dI" % NMODES, X, IDS - B))


def geom(mode):
    """(stage rows H, phase-detect rows p, window row, band row, active rows, first active row) of a mode, from its table rows."""
    i = ids().index(mode)
    s0, s1, cr = row(S0, i), row(S1, i), row(CROP, i)
    return (s0[12] + s0[13] + s0[14], s1[13], s0[10] + s0[11], cr[3], s0[13], s0[10] + s0[11] + s0[12])


def xgeom(mode, rec):
    """geom() plus (frame width, Lrc output width, Lrc output rows): the column and output terms, used only to classify fields."""
    s0 = row(S0, ids().index(mode))
    _, _, target = N.pair_inputs(rec)
    return geom(mode) + (s0[3] + s0[4] + s0[5], target[0], target[1])


def matrix_rows():
    out, r = [], 0
    while struct.unpack_from("<I", X, MATRIX - B + MROW * r)[0]:
        out.append(struct.unpack_from("<I", X, MATRIX - B + MROW * r)[0])
        r += 1
    base = min(out)
    return {p - base: k for k, p in enumerate(out)}, base


def check_sensor_facts():
    ii = ids()
    idx = [ii.index(m) for m in MODES]
    assert idx == [2, 3, 4, 5], idx
    col = struct.unpack_from("<%dI" % NMODES, X, COLMAP - B)
    assert all(col[i] == MCOL for i in idx) and sum(c == MCOL for c in col) == 4, "column 2 is not exactly the four 4K modes'"
    for tbl in (CROP, S0, S1, LC):
        assert all(row(tbl, i) == row(tbl, idx[0]) for i in idx), f"table {tbl[0]:#x}: the four modes' rows differ"
    ro = [row(RO, i) for i in idx]
    assert all(r[:18] == ro[0][:18] and r[19:] == ro[0][19:] for r in ro), "read-out rows differ beyond field 18"
    s0, s1, cr, lc = row(S0, idx[0]), row(S1, idx[0]), row(CROP, idx[0]), row(LC, idx[0])
    assert (s0[4], s0[13], s0[10:16]) == (4320, 2430, [12, 2, 8, 2430, 8, 2]), s0
    assert (s1[13], s1[15], cr[3], cr[9], lc[4], lc[6], ro[0][11], ro[0][20], ro[0][21]) == (114, 36, 222, 5, 535, 631, 58, 679, 679)
    # the full-height values: the still / live-view modes that read the full height (0xa000 full res, 0x5020 3x3, 0x5000 6x6)
    for m in (0xA000, 0x5020, 0x5000):
        i = ii.index(m)
        assert row(CROP, i)[3] == 0 and row(CROP, i)[9] == 0 and row(LC, i)[6] == 151, hex(m)
    for m in (0x5020, 0x5000):
        i = ii.index(m)
        assert row(S1, i)[13] == 134, hex(m)
    # the picture records' phase-detect total (+0x290) = stream-1 [9] + [13] + [15] in every family; the 2x2 family keeps [9] = 113 and
    # [15] = 36 in both its windows (0x8c0 and 0x7e0), so only [13] moves
    assert row(S1, ii.index(0x7E0))[9] == s1[9] == 113 and row(S1, ii.index(0x7E0))[15] == s1[15] == 36
    for at, m in ((0xDF6844, 0x8C0), (0xDF50D4, 0x7E0), (0xDF7FB4, 0x821), (0xDFF4E4, 0xB20)):
        r = row(S1, ii.index(m))
        assert u16(X, at - B + 0x290) == r[9] + r[13] + r[15], hex(m)
    # LC[4] = base + binning x band row (2x2: 91 + 2 x 222, crop mode 0x7e0: 91 + 2 x 362)
    assert lc[4] == 91 + 2 * cr[3] and row(LC, ii.index(0x7E0))[4] == 91 + 2 * row(CROP, ii.index(0x7E0))[3]
    # register matrix: the window rows and +0x90 = 33 + n in sensor mode 0x14
    rows, _ = matrix_rows()
    cell = lambda off, c: X[MATRIX - B + MROW * rows[off] + 4 + c]
    full_cols = [c for c in range(25) if cell(0x20, c) == 1]
    for c in range(25):
        k = 2 if cell(0x24, c) > 31 else 1
        assert cell(0x20, c) + cell(0x24, c) // k == 31, (c, cell(0x20, c), cell(0x24, c))
    for c in (1, 2, 6):                                     # the three columns of sensor mode 0x14
        assert cell(0, c) == 0x14 and cell(0x90, c) == 33 + cell(0x24, c), (c, cell(0x90, c), cell(0x24, c))
    assert all(cell(0x24, c) in (30, 60) for c in full_cols)
    for off, (old, new) in MATRIX_EDITS.items():
        assert cell(off, MCOL) == old, (hex(off), cell(off, MCOL))
    assert new == 33 + 30
    sel, _ = S.records(BUILD)
    for p, modes in USES.items():
        assert all(sel[m] == [PAIRS[p]["L"], PAIRS[p]["R"]] for m in modes), {hex(m): sel[m] for m in modes}
    users = sorted(hex(m) for m, r in sel.items() if set(r) & {a for pp in PAIRS.values() for a in pp.values()})
    assert users == sorted(hex(m) for m in MODES), users
    geo = {}
    for r in range(48):
        mid = struct.unpack_from("<I", X, GEO - B + 12 * r)[0]
        if mid in MODES:
            geo[mid] = GEO + 12 * r
    assert sorted(geo) == sorted(MODES) and all(u16(X, a - B + 10) == 222 for a in geo.values())
    return idx, geo, rows


def cells(idx, geo, rows):
    """Table sites: one per table over the rows of indices 2..5, the geometry rows, and the three matrix cells."""
    p_new, ro_len = 134, 679 + (12 + 2 + 8 + NEW_H + 8 + 2 - 2462) // 4 + 1       # 2912 rows: 679 + 112.5 -> 792
    assert ro_len == 792
    edits = {CROP: {3: 0, 9: 0}, S0: {13: NEW_H}, S1: {13: p_new}, LC: {4: 91, 6: 151}, RO: {11: 33 + 30, 20: ro_len, 21: ro_len}}
    names = {CROP: "crop", S0: "stream-0 window", S1: "stream-1 (phase detect)", LC: "LC", RO: "read-out"}
    sites, imgcells = [], []
    for tbl, ed in edits.items():
        base, n = tbl
        lo, hi = base + n * idx[0], base + n * (idx[-1] + 1)
        old = bytearray(rd(lo, hi - lo))
        new = bytearray(old)
        for i in idx:
            for f, v in ed.items():
                struct.pack_into("<H", new, n * (i - idx[0]) + 2 * f, v)
                imgcells.append((base + n * i + 2 * f, v))
        sites.append({"kind": "S", "addr": hex(lo), "old": bytes(old).hex(), "new": bytes(new).hex(), "where": "file",
                      "note": f"{names[tbl]} table {base:#x}, rows of indices 2-5 (0x820, 0x2820, 0x8c0, 0x28c0): "
                              + ", ".join(f"field {f} {u16(old, 2 * f)} -> {v}" for f, v in ed.items())})
    glo, ghi = min(geo.values()), max(geo.values()) + 12
    old = bytearray(rd(glo, ghi - glo))
    new = bytearray(old)
    for m, a in geo.items():
        struct.pack_into("<H", new, a - glo + 10, 0)
        imgcells.append((a + 10, 0))
    sites.append({"kind": "S", "addr": hex(glo), "old": bytes(old).hex(), "new": bytes(new).hex(), "where": "file",
                  "note": "geometry table (12-byte rows by mode id): band row 222 -> 0 in the rows of " + ", ".join(hex(m) for m in sorted(geo))})
    for off, (o, nv) in MATRIX_EDITS.items():
        a = MATRIX + MROW * rows[off] + 4 + MCOL
        sites.append({"kind": "S", "addr": hex(a), "old": "%02x" % o, "new": "%02x" % nv, "where": "file",
                      "note": f"register matrix row {rows[off]} (shadow +{off:#x}), column 2 (sensor mode 0x14, used by the four 4K modes only): "
                              f"{o} -> {nv} ({'window start block' if off == 0x20 else 'window half-height n' if off == 0x24 else '33 + n'})"})
        imgcells.append((a, bytes([nv])))
    return sites, imgcells, {"p": p_new, "readout_length": ro_len}


# ---------------------------------------------------------------- the row model

def pair(at):
    return {h: rd(a, SIZE) for h, a in at.items()}


TERMS = {"H": lambda g: g[0], "p": lambda g: g[1], "row": lambda g: g[2], "band": lambda g: g[3], "H+row": lambda g: g[0] + g[2],
         "H+row+p": lambda g: g[0] + g[2] + g[1], "p+row": lambda g: g[1] + g[2], "act": lambda g: g[4], "first": lambda g: g[5],
         "act+first": lambda g: g[4] + g[5],
         # column and output terms: a field that follows one of these is left stock (the design keeps the width and the front end)
         "W": lambda g: g[6], "oW": lambda g: g[7], "oH": lambda g: g[8]}
ROWTERMS = ("H", "p", "row", "band", "H+row", "H+row+p", "p+row", "act", "first", "act+first")
CANDS = [("H", Fr(1)), ("H", Fr(1, 2)), ("H", Fr(1, 4)), ("H+row", Fr(1)), ("H+row", Fr(1, 2)), ("row", Fr(1)), ("row", Fr(1, 2)),
         ("p", Fr(1)), ("p", Fr(1, 2)), ("H+row+p", Fr(1)), ("p+row", Fr(1)), ("band", Fr(1)),
         ("act", Fr(1)), ("act", Fr(1, 2)), ("act", Fr(1, 4)), ("first", Fr(1)), ("first", Fr(1, 2)), ("act+first", Fr(1))]
OUTCANDS = [(t, k) for t in ("W", "oW", "oH") for k in (Fr(1), Fr(1, 2), Fr(1, 4), Fr(1, 8))]
ROUND = {"floor": lambda v, m: (v // m) * m, "ceil": lambda v, m: -((-v) // m) * m, "near": lambda v, m: ((v + Fr(m, 2)) // m) * m}


def value(rule, base_v, g0, g):
    kind, k, rnd = rule
    if kind == "const":
        return base_v
    if kind == "band" and k == 1 and rnd is None and base_v == g0[3]:
        return g[3]
    v = base_v + k * (TERMS[kind](g) - TERMS[kind](g0))
    if rnd:
        how, m, c = rnd
        v = ROUND[how](TERMS[kind](g) * k + c, m)
    return v


def fits(cands, v, gx):
    """The first candidate rule (kind, k, rounding or None) that every pair of the family obeys exactly."""
    for kind, k in cands:
        if all(Fr(v["A"]) + k * (TERMS[kind](gx[n]) - TERMS[kind](gx["A"])) == v[n] for n in v):
            return (kind, k, None)
    for kind, k in cands:                                       # a rounded term: round(k * term + c, m), one c for the family
        for how in ROUND:
            for m in (1, 4, 8, 16):
                c0 = v["A"] - k * TERMS[kind](gx["A"])            # only constants that can give pair A's value
                for c in range(int(c0) - m - 1, int(c0) + m + 2):
                    if all(ROUND[how](k * TERMS[kind](gx[n]) + c, m) == v[n] for n in v):
                        return (kind, k, (how, m, c))
    return None


def fit_rules(M, fam):
    """Classify every 16-bit field that differs within the 2x2 family and is not written by the planner or a packer:
       row rule (H, p, window row, band row)  -> applied to the design
       column / output rule (frame width, Lrc output size) -> left stock (the design keeps the width and the front end)
       neither -> listed, and asserted to be none."""
    recs = {n: pair(a) for n, (a, _) in fam.items()}
    gx = {n: xgeom(m, recs[n]) for n, (_, m) in fam.items()}
    planner = set(range(N.COLS[0], N.COLS[1], 2))
    rules, column_like, unexplained, ambiguous = {}, {}, {}, {}
    for h in "LR":
        rules[h], column_like[h], unexplained[h], ambiguous[h] = {}, [], [], []
        for o in range(0, SIZE, 2):
            v = {n: u16(recs[n][h], o) for n in recs}
            if len(set(v.values())) == 1 or o in M.packer or o in planner:
                continue
            r_row, r_out = fits(CANDS, v, gx), fits(OUTCANDS, v, gx)
            if r_row and r_out:
                ambiguous[h].append((hex(o), str(r_row), str(r_out)))
            if r_row and not r_out:
                rules[h][o] = r_row
            elif r_out:
                column_like[h].append(o)
            else:
                unexplained[h].append(o)
    return rules, column_like, {n: g[:6] for n, g in gx.items()}, unexplained, ambiguous


def apply_rules(rules, base, g0, g):
    out = {}
    for h in "LR":
        r = bytearray(base[h])
        for o, rule in rules[h].items():
            v = value(rule, Fr(u16(base[h], o)), g0, g)
            assert v.denominator == 1 and 0 <= v < 0x10000, (h, hex(o), rule, v)
            struct.pack_into("<H", r, o, int(v))
        out[h] = bytes(r)
    return out


def build_pair(M, rules, base, g0, g, frame, crop, target):
    mod = apply_rules(rules, base, g0, g)
    return N.assemble(M, mod, target, frame=frame, crop=crop, mirror_as=base)


def frame_crop(mode, H=None):
    """Lrc frame and crop of a mode's pair, from its stream-0 row (as N.pair_inputs reads them from a stock pair)."""
    s0 = row(S0, ids().index(mode))
    h = s0[13] if H is None else H
    return (s0[3] + s0[4] + s0[5], s0[12] + h + s0[14]), (s0[3], s0[12], s0[4], h)


def main():
    idx, geo, mrows = check_sensor_facts()
    sites, imgcells, sfacts = cells(idx, geo, mrows)
    M = F.Model(A)
    rules, column_like, gm, unexplained, ambiguous = fit_rules(M, FAMILY)
    print("rules", {h: len(r) for h, r in rules.items()}, "column/output", {h: len(c) for h, c in column_like.items()},
          "unexplained", {h: [hex(o) for o in u] for h, u in unexplained.items()}, "ambiguous", ambiguous)
    # rules in H / window row only, checked on the other families too
    other = {n: (pair(a), geom(m)) for n, (a, m) in OTHER.items()}
    other_bad = []
    for h in "LR":
        for o, rule in rules[h].items():
            if rule[0] in ("H", "row", "H+row", "act", "first", "act+first") and rule[2] is None:
                for n, (rec, g) in other.items():
                    want = value(rule, Fr(u16(pair(FAMILY["A"][0])[h], o)), gm["A"], g)
                    if want != u16(rec[h], o):
                        other_bad.append((h, hex(o), n, str(rule), int(want), u16(rec[h], o)))
    # self-test: rebuild each real pair from another of a different height (and width): rows by the model, columns by the planner. Compared
    # over the fields the design changes by rule and the planner's range; the width and output fields outside it are the base's by design
    # (the A1 II has no two 2x2 pairs of the same width and different height, so those cannot be cross-checked; the design keeps both).
    selftest = {}
    planner = range(N.COLS[0], N.COLS[1], 2)
    for name, frm_n, to_n in (("A_from_crop", "crop", "A"), ("crop_from_A", "A", "crop"), ("s35a_from_A", "A", "s35a"), ("A_from_s35b", "s35b", "A")):
        base, want = pair(FAMILY[frm_n][0]), pair(FAMILY[to_n][0])
        frame, crop, target = N.pair_inputs(want)
        got, _ = build_pair(M, rules, base, gm[frm_n], gm[to_n], frame, crop, target)
        diff = {h: [hex(o) for o in sorted(set(rules[h]) | set(planner)) if got[h][o:o + 2] != want[h][o:o + 2]] for h in "LR"}
        selftest[name] = diff
        print(f"self-test {name}: rule/planner fields that differ L {len(diff['L'])} R {len(diff['R'])}", {h: d[:12] for h, d in diff.items() if d})
    print("H/row rules off on the other families:", other_bad[:20])
    if "--check" in sys.argv:
        return
    exact = all(not d["L"] and not d["R"] for d in selftest.values())
    assert exact, "the row model does not rebuild the stock pairs"
    # The fields the rules leave stock follow the width or the output (or both with rows fixed): none of them may be a field the A7 IV's
    # own row model (build_fhstage, fitted on A7 IV designs that changed only the rows; evidence/a7s3/a7iv_fhstage_rules.json) moves.
    a7rows = json.loads((ROOT / "evidence/a7s3/a7iv_fhstage_rules.json").read_text(encoding="utf8"))
    a7_row_fields = {h: {int(r[0], 16) for r in a7rows[h]} for h in "LR"}
    missing = {h: [hex(o) for o in sorted(a7_row_fields[h]) if o not in rules[h] and not N.COLS[0] <= o < N.COLS[1]] for h in "LR"}
    assert not missing["L"] and not missing["R"], ("A7 IV row fields without an A1 II row rule", missing)
    assert not other_bad, other_bad
    # the design pairs
    g_new = (NEW_H + 16, sfacts["p"], gm["A"][2], 0, NEW_H, gm["A"][5])
    frame, crop = frame_crop(0x8C0, NEW_H)
    assert frame == (4332, NEW_H + 16) and crop == (6, 8, 4320, NEW_H)
    if BOTTOM:              # stage rows, active rows stock; window row, first active row and band row move down by BOTTOM_ROWS; the frame-level
        #                   phase-detect rows are the full frame's (the sensor sends the whole height)
        g_new = (gm["A"][0], sfacts["p"], gm["A"][2] + BOTTOM_ROWS, BOTTOM_ROWS, gm["A"][4], gm["A"][5] + BOTTOM_ROWS)
        frame, crop = frame_crop(0x8C0)
    recs, lrc, nfields, post_lrc = {}, {}, {}, {}
    for p, at in PAIRS.items():
        base = pair(at)
        assert N.pair_inputs(base) == (frame_crop(0x8C0)[0], frame_crop(0x8C0)[1], STOCK_OUT), (p, N.pair_inputs(base))
        rec, facts = build_pair(M, rules, base, gm["A"], g_new, frame, crop, OUT)
        lint, _ = LINT.lint_design_records(rec["L"], rec["R"])
        broken = {r: d for r, (ok, d) in lint.items() if not ok}
        assert not broken, (p, broken)
        lrc[p] = {}
        for h in "LR":
            k = LINT.lrc(rec[h])
            lrc[p][h] = {"input": list(k["in"]), "output": list(k["out"]), "step_q12": list(k["step"]), "start": list(k["start"])}
            assert k["in"][1] == (2446 if BOTTOM else NEW_H + 16) and u16(rec[h], 0x95E) == (BOTTOM_ROWS if BOTTOM else 0)
            moved = [hex(o) for o in range(0x174, 0x1D8, 2) if rec[h][o:o + 2] != base[h][o:o + 2]]
            post_lrc.setdefault(p, {})[h] = {"row_pad": [u16(base[h], 0x186), u16(rec[h], 0x186)], "fields": moved}
            if not REAL:            # only the Lrc output's row padding may move (the movie row rule: padded rows = rows + 2 x the fit's pad)
                assert set(moved) <= {"0x17a", "0x182", "0x186"}, (p, h, moved)
        recs[p] = rec
        nfields[p] = {h: sum(rec[h][x:x + 2] != base[h][x:x + 2] for x in range(0, SIZE, 2)) for h in "LR"}
        for h in "LR":
            sites.append({"kind": "R", "addr": hex(at[h]), "old": base[h].hex(), "new": bytes(rec[h]).hex(), "where": "file",
                          "note": f"{'left' if h == 'L' else 'right'} picture record of modes {', '.join(hex(m) for m in USES[p])}: first stage "
                                  f"{NEW_H + 16} rows (crop 4320 x {NEW_H}), "
                                  + (f"kept whole by Lrc ({OUT[0]} x {OUT[1]} front end); " if REAL else f"squeezed by Lrc into the stock {OUT[0]} x {OUT[1]} front end; ")
                                  + f"{nfields[p][h]} fields differ"})
    sites.sort(key=lambda s: int(s["addr"], 16))
    # stored records: the A1 II's own calculator, stock and with the cells, NTSC (60 Hz) and PAL (50 Hz) timing
    f = E.CONSTS[BUILD]["fields"]
    pal = [(f[0x2C], rd(f[0x30], 24 * NMODES))]
    stored = {}
    for system, base in (("ntsc", []), ("pal", pal)):
        st, l1 = E.records(BUILD, base)
        de, l2 = E.records(BUILD, base + imgcells)
        assert not l1 and not l2 and all(st[m][2] is None and de[m][2] is None for m in st)
        changed_modes = sorted(m for m in st if st[m][1] != de[m][1])
        assert changed_modes == sorted(MODES), [hex(m) for m in changed_modes]
        stored[system] = {m: (bytearray(st[m][1]), bytearray(de[m][1])) for m in MODES}
    ids_all = ids()
    recs_out = {}
    for m in MODES:
        var = {}
        for system in ("ntsc", "pal"):
            s, d = stored[system][m]
            assert s[4:8] == b"\x02\x01\x02\x01", s[4:8].hex()
            d[6], d[7] = PAV
            ex = {"height": u16(d, 0x66), "pdaf_rows": u16(d, 0x8C), "pdaf_15": u16(d, 0x90), "lc4": u16(d, 0xFE), "band": u16(d, 0x10A),
                  "lc6": u16(d, 0x16A), "readout_length": u16(d, 0x148)}
            assert ex == {"height": NEW_H, "pdaf_rows": sfacts["p"], "pdaf_15": 36, "lc4": 91, "band": 0, "lc6": 151,
                          "readout_length": sfacts["readout_length"]}, ex
            var[system] = (bytes(s), bytes(d))
        offs = sorted({k for s, d in var.values() for k in range(len(s)) if s[k] != d[k]})
        timing_only = [hex(k) for k in range(0, 0x170, 2) if k not in offs and var["ntsc"][0][k:k + 2] != var["pal"][0][k:k + 2]]
        recs_out[hex(m)] = {"index": ids_all.index(m), "offsets_that_differ": [hex(k) for k in offs],
                            "ntsc_pal_stock_differ_elsewhere_untouched": timing_only,
                            **{sy: {"stock": var[sy][0].hex(), "design": var[sy][1].hex(),
                                    "words": {hex(k): [u16(var[sy][0], k), u16(var[sy][1], k)] for k in range(0, 0x170, 2)
                                              if var[sy][0][k:k + 2] != var[sy][1][k:k + 2]}} for sy in var}}
        print(f"stored record {m:#06x}: {len(offs)} bytes are sites {[hex(k) for k in offs]}")
    ev = ROOT / "evidence/a1m2/sensor"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / f"{NAME}_stored_records_emu.json").write_text(json.dumps({
        "about": "Stored drive-parameter records (0x170 bytes) of the four 4K modes, from the A1 II's own calculator 0x132320 "
                 "(build/emu_drvparam.py a1m2_400), stock and with the design's table cells, plus the vertical sampling ratio 27/16 at +6/+7 "
                 "(over +4/+5 = 2/1), with the 60 Hz (ntsc) and the 50 Hz (pal) timing table. The sites are the union of the bytes either variant changes.",
        "records_base_in_emulation": hex(f[0x10]), "record_bytes": 0x170, "modes": recs_out}, indent=1) + "\n", encoding="utf8", newline="\n")
    (ev / f"{NAME}_selftest.json").write_text(json.dumps({
        "about": "build/build_og_a1m2.py self-test: the row model (fitted on the A1 II's 2x2-binned pairs) with build_fhnative.assemble (planner "
                 "columns, movie row rule, firmware packers) rebuilds each real pair from another",
        "family": {n: {"pair": {h: hex(a) for h, a in at.items()}, "mode": hex(m), "geometry_H_p_row_band": geom(m)} for n, (at, m) in FAMILY.items()},
        "rules": {h: {hex(o): f"{r[0]}*{r[1]}" + (f" rounded {r[2]}" if r[2] else "") for o, r in sorted(rules[h].items())} for h in "LR"},
        "fields_left_stock_column_or_output_dependent": {h: [hex(o) for o in v] for h, v in column_like.items()},
        "fields_left_stock_no_simple_rule": {h: [hex(o) for o in v] for h, v in unexplained.items()},
        "a7iv_row_fields_all_covered": True,
        "H_or_row_rules_that_other_families_do_not_follow": other_bad,
        "rebuilds": selftest, "exact": exact}, indent=1) + "\n", encoding="utf8", newline="\n")
    out = {"design": NAME, "build": BUILD, "camera": "ILCE-1M2 (A1 II), firmware 4.00",
           "title": "A1 II open gate, sensor side: 4320 x 2880 (3:2, 2x2 binned, full height) in modes 0x820/0x2820/0x8c0/0x28c0, first stage "
                    + ("4332 x 2896, every row kept by the first scaler (4320 x 2880 front end); the second scaler makes 3840 x 2560 at 1.125 on both axes"
                       if REAL else "4332 x 2896 squeezed into the stock 4320 x 2430 front end, vertical sampling ratio 27/32"),
           "status": "built from the firmware files and emulated in parts; never run on a camera",
           "artifact": "cpapp-b.bin", "artifact_sha256": SHA, "generated_by": "build/build_og_a1m2.py",
           "ported_from": {"design": "ogsq_v3", "build": "a7iv_602",
                           "how": "the A7 IV's mechanism (full-height window, Lrc squeeze, 27/32) rebuilt on the A1 II's own tables and records; "
                                  "the window is the sensor's own vertical window registers in the 4K sensor mode (the A7 IV switched modes)"},
           "modes": [hex(m) for m in MODES], "mode_indices": idx,
           "summary": {"window": [4320, NEW_H], "stock_window": [4320, 2430], "first_stage": [4332, NEW_H + 16], "front_end": list(OUT),
                       "sensor": {"mode": "0x14 (2x2 binning)", "window_registers": {"start_block": [6, 1], "half_height": [25, 30], "reg_0x90": [58, 63]}},
                       "pdaf": sfacts, "line_periods_per_frame": {"23.98p": 6320, "29.97p": 5056, "25p": 5888}, "sensor_lines_read": 2912,
                       "lrc": lrc, "record_fields_changed": nfields, "post_lrc_row_padding": post_lrc, "sites": len(sites), "bytes": sum(len(s["old"]) // 2 for s in sites),
                       "expected_working_state": {"crop": [4320, NEW_H], "front_end": list(OUT), "second_scaler_takes": "the whole front end",
                                                  "file": [3840, 2560]}},
           "patches": sites, "record_size": 0x170,
           "stored_records": {k: {"index": v["index"], "offsets_that_differ": v["offsets_that_differ"],
                                  "ntsc": {"stock": v["ntsc"]["stock"], "design": v["ntsc"]["design"]},
                                  "pal": {"stock": v["pal"]["stock"], "design": v["pal"]["design"]}} for k, v in recs_out.items()},
           "stored_record_note": "RAM, filled by the camera at start-up from the tables; records base = the drive-parameter object's +0x10 "
                                 "(emulation " + hex(f[0x10]) + ") + index x 0x170; the write level finds each mode's record through the pointer chain",
           "stored_record_extra": [] if REAL else [{"offset": "0x6", "old": "02", "new": "%02x" % PAV[0], "note": "vertical sampling ratio, numerator (+4/+5 = 2/1 kept)"},
                                   {"offset": "0x7", "old": "01", "new": "%02x" % PAV[1], "note": "vertical sampling ratio, denominator"}],
           "not_shown": ["that the sensor reads 2,880 binned rows in mode 0x14 with s = 1, n = 30 (the window rule holds in every stock column; "
                         "no stock column is 2x2 at full height)",
                         "the margins a full-height 2x2 window gives (the stock 4K margins 8 / 8 + 2 trailing are kept; the full-res still mode has 12 "
                         "physical rows each side)",
                         "+0x90 = 63 (33 + n holds in the three 0x14 columns)",
                         "the resize fit with 27/16 over 2/1 on this body (CalcRC / the RC calc were not emulated on the A1 II)",
                         "that the raw write buffer holds the 2,896-row stage (modding/A1M2_PORT_DMM_SIZE.md)",
                         "anything on a camera"],
           "evidence": [f"evidence/a1m2/sensor/{NAME}_selftest.json", f"evidence/a1m2/sensor/{NAME}_stored_records_emu.json",
                        "evidence/a1m2/sensor_matrix_dump.txt", "evidence/a1m2/modes_overview.txt"]}
    (ROOT / "modding/designs" / f"{NAME}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print(json.dumps(out["summary"]))


if __name__ == "__main__":
    main()
