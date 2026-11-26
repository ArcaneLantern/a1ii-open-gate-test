"""Write a1m2_expected.h for a1m2read.c from the A1 II 4.00 files and the port designs (A1 II port, 2026-11-26).

  C:\\Python313\\python.exe -B gen_a1m2.py

helper_fx30/gen_fx30.py with this build's files, designs and addresses (modding/A1M2_PORT.md, evidence/a1m2/helper_constants.json). Everything
the helper compares against is taken here from the extracted 4.00 update and from modding/designs/{ogsq_a1m2_v1, outsz2560_a1m2_v1,
ogfile2560_hs_s_a1m2_v2, lcdfill_a1m2_v1}.json. The helper holds no other constant about the camera except the addresses listed at the top of
this file.
  - The sensor design's 13 table/record/matrix sites are hard sites (stock or target, counted). The real-rows alternative (ogh2880_a1m2_v1)
    has the same table and matrix bytes and other record bytes: its records read OTHER here (R5's own result says what it wrote).
  - The four stored drive-parameter records are soft sites: the camera computes them at start-up (NTSC or PAL table) and keeps run-time
    bytes in them, so they need not equal the emulated ones; the check prints their bytes and the PC reads the design offsets.
  - The output-size words are soft (zero until a movie mode has run), the screen words soft (the screen step is optional).
  - The XAVC S-I step (I19) and the C3 routine (C19, in appFw.so) are not listed: their own libraries check and report their sites.
Also writes a1m2_expected.json (what the PC checks against) and a1m2_reference.json (what the PC needs to read a dump). Read-only on the inputs.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EX = ROOT / "work/extracted/a1m2_400/0700_part_image/dev"
DES = ROOT / "modding/designs"
sys.path.insert(0, str(ROOT / "build"))

BASE = 0x108000
LABEL = "a1m2read_v2"                                 # v2 (kit v2): + the resize view page, the margin page, the fehold word
CP_LO, CP_HI = 0xC0000, 0x2700000                     # coprocessor addresses a read may have: its logs, image and RAM tables
AVCAM_PHYS, AVCAM_RESERVE = 0x401000000, "@0x401000000"   # kemco: memrsv=0x01000000@0x401000000:ex, as the A7 IV
ID_FILES = {"/libmpr.so": "nflasha15/lib/libmpr.so", "/libsencore.so": "nflasha15/lib/libsencore.so", "/libJiritsu.so": "nflasha15/lib/libJiritsu.so"}
# four 4 KB pages of coprocessor CODE that no design touches: a low code page, the record selector's (0x279f20), the movie size table's
# set-up (0x501834) and the drive-parameter table map (constructor caller 0xa0d5ec); each differs from every other build on disk
ID_PAGES = (0x128000, 0x279000, 0x501000, 0xA0D000)
# The A1 II sensor's register matrix: 100 rows of 32 bytes (the register shadow's address, then one byte per column, 28 columns) and a
# zero row, then the column map (44 words, one per drive mode). Shadow addresses 0x13029b0..0x1302e2c.
MATRIX, MATRIX_ROWS, MROW, COLMAP, IDS, NMODES = 0x11EE600, 100, 32, 0x11EF2A0, 0xE9EB40, 44
RECS, REC = 0x24DBA14, 0x170
SIZE_TABLE = 0x1938488
DESIGNS = ("ogsq_a1m2_v1", "outsz2560_a1m2_v1", "ogfile2560_hs_s_a1m2_v2", "lcdfill_a1m2_v1", "ogh2880_a1m2_v1", "fehold_a1m2_v1")
UNIT, DESC, DSIZE, CLIP, NDESC = 0x3AB234, 0x3AB2D4, 0x90, 0x3A9158, 686    # build_ogfile.OTHER_BUILDS["a1m2_400"] (A1M2_PORT_ENCODER.md)
PANEL_REAR, PANEL_EVF = 0x1A1C638, 0x1A1C768          # rear panel type byte (3 = 3:2 expected) and the viewfinder's (A1M2_PORT_SCREEN.md)
# The pages the dump reads beyond the display pages (taken from the screen design's sites and guards below, one page each):
DUMP_FIXED = (("shadow", 0x1302000, 1), ("matrix", 0x11EE000, 2), ("sizetable", 0x1938000, 1), ("records", 0x24DB000, 5),
              ("kprint", 0xE0000, 32), ("bootlog", 0xC0000, 8), ("dmmglobals", 0x1971000, 2), ("dmmrecs", 0x2481000, 2),
              ("sensorobject", 0x1790000, 1),
              # the resize module (weak addresses: port_addr from the FX2's, one or two votes; the dump decoder searches these pages for known
              # sizes) and the resize working structure
              ("resizestate", 0x194F000, 2), ("resizework", 0x1626000, 1),
              # the panel records: rear panel type byte 0x1a1c638 (3 = 3:2), viewfinder 0x1a1c768 (build/build_lcd_a1m2.py)
              ("paneltype", 0x1A1C000, 1),
              # kit v2: the resize set-up's view (0x16237b0, 0x54 bytes: flag +5, crop +0x38, first-scaler size +0x3c, output +0x40; the
              # caller 0x527062 passes it to 0x521438) and the margin table (0x1951514 +0xa..+0x18, its switch word 0x1951e58)
              ("view", 0x1623000, 1), ("margin", 0x1951000, 1))


def c_bytes(b):
    return "{" + ",".join(str(x) for x in b) + "}"


def design(n):
    return json.loads((DES / f"{n}.json").read_text(encoding="utf8"))


def site_name(p):
    n = p["note"]
    if p["kind"] == "R":
        side = "left" if n.startswith("left") else "right"
        return ("record_28c0_" if "0x2820" in n.split(":")[0] else "record_8c0_") + side
    for k, v in (("crop", "crop"), ("stream-0", "window"), ("stream-1", "pdaf"), ("LC", "lc"), ("read-out", "readout"), ("geometry", "geometry"),
                 ("register matrix row 8 ", "matrix_start"), ("register matrix row 9 ", "matrix_half"), ("register matrix row 18 ", "matrix_r90")):
        if n.startswith(k):
            return v
    raise SystemExit("site without a name: " + n[:60])


def main():
    cp = (EX / "nflasha8/cpapp-b.bin").read_bytes()
    av = (EX / "nflasha3/av-cam.bin").read_bytes()
    lm = (EX / "nflasha15/lib/libmpr.so").read_bytes()
    og, oz, fl, sc, rr, fh = (design(n) for n in DESIGNS)
    sha_cp = hashlib.sha256(cp).hexdigest()
    assert og["artifact_sha256"] == sha_cp == rr["artifact_sha256"] and og["build"] == "a1m2_400"
    assert fl["artifact_sha256"] == {"libmpr.so": hashlib.sha256(lm).hexdigest(), "av-cam.bin": hashlib.sha256(av).hexdigest()}
    # the real-rows alternative has the same table and matrix sites (S) as the default, only other record bytes (R)
    assert [(p["addr"], p["old"], p["new"]) for p in og["patches"] if p["kind"] == "S"] == [(p["addr"], p["old"], p["new"]) for p in rr["patches"] if p["kind"] == "S"]
    out, blobs = [], []

    def blob(b):
        blobs.append(f"static const unsigned char B{len(blobs)}[] = {c_bytes(b)};")
        return f"B{len(blobs) - 1}"

    out.append(f'#define A1M2_LABEL "{LABEL}"\n#define CP_LO {CP_LO:#x}U\n#define CP_HI {CP_HI:#x}U\n#define AVCAM_PHYS {AVCAM_PHYS:#x}UL\n'
               f'#define AVCAM_RESERVE "{AVCAM_RESERVE}"')
    out.append("struct id_file { const char *name; unsigned char sha256[32]; };\nstruct id_page { unsigned int address; unsigned char sha256[32]; };\n"
               "struct cp_site { const char *name; unsigned int address, length; const unsigned char *stock, *target; int soft;\n"
               "                 const unsigned short *doff; const unsigned char *dval; unsigned int ndiff; };   /* target = stock + these, when target is null */\n"
               "struct mp_site { unsigned long offset; unsigned int length; const unsigned char *stock, *target; };\n"
               "struct av_guard { const char *name; unsigned long offset; unsigned int length; unsigned char sha256[32]; };\n"
               "struct dump_range { const char *name; unsigned int address, pages; };")
    rows = [f'    {{"{n}", {c_bytes(hashlib.sha256((EX / p).read_bytes()).digest())}}},' for n, p in ID_FILES.items()]
    out.append("static const struct id_file id_files[] = {\n" + "\n".join(rows) + "\n};")
    # ---- coprocessor sites
    sites = []
    for p in sorted(og["patches"], key=lambda p: int(p["addr"], 16)):
        a, old, new = int(p["addr"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        assert cp[a - BASE:a - BASE + len(old)] == old and len(old) == len(new)
        sites.append((site_name(p), a, old, new, 0))
    assert len({s[0] for s in sites}) == 13
    ids = list(struct.unpack_from("<%dI" % NMODES, cp, IDS - BASE))
    for m, sr in og["stored_records"].items():            # soft: computed at start-up, run-time bytes; the PC reads the design offsets
        assert sr["index"] == ids.index(int(m, 16))
        sites.append((f"stored_record_{m}", RECS + sr["index"] * REC, bytes.fromhex(sr["ntsc"]["stock"]), bytes.fromhex(sr["ntsc"]["design"]), 1))
    for s in oz["sites"]:                                 # soft: the size table is zero until a movie mode has run
        sites.append(("outsize", int(s["ram_address"], 16), bytes.fromhex(s["old"]), bytes.fromhex(s["new"]), 1))
    for k, g in enumerate(oz["guards"]):
        sites.append((f"outsize_guard{k}", int(g["ram_address"], 16), bytes.fromhex(g["bytes"]), None, 1))
    for k, s in enumerate(sc["sites"]):                   # soft: the screen step is optional (apply --no-screen); reported, not counted
        a, old = int(s["ram_address"], 16), bytes.fromhex(s["old"])
        if BASE <= a < BASE + len(cp):
            assert cp[a - BASE:a - BASE + 4] == old
        sites.append((f"screen{k}", a, old, bytes.fromhex(s["new"]), 1))
    for s in fh["sites"]:                                 # soft (kit v2): the code word F16 writes (resize set-up 0x521438: the override skipped)
        a, old = int(s["ram_address"], 16), bytes.fromhex(s["old"])
        assert cp[a - BASE:a - BASE + 4] == old
        sites.append(("fehold", a, old, bytes.fromhex(s["new"]), 1))
    pages = {x & ~0xFFF for _, a, o, _, _ in sites for x in (a, a + len(o) - 1) if a < BASE + len(cp)}
    assert not any(p in pages for p in ID_PAGES), "an identity page holds a design site"
    rows = [f"    {{{a:#x}, {c_bytes(hashlib.sha256(cp[a - BASE:a - BASE + 4096]).digest())}}}," for a in ID_PAGES]
    out.append("static const struct id_page id_pages[] = {\n" + "\n".join(rows) + "\n};")
    rows = []
    for name, a, old, new, soft in sites:
        assert CP_LO <= a and a + len(old) <= CP_HI and len(old) <= 3072
        if new is not None and len(old) > 64:              # a long site: its target as the stock bytes with a list of changed bytes (a1m2read.c same_patched)
            ks = [k for k in range(len(old)) if old[k] != new[k]]
            blobs.append("static const unsigned short D%d[] = {%s};" % (len(blobs), ",".join(str(k) for k in ks)))
            doff = "D%d" % (len(blobs) - 1)
            rows.append(f'    {{"{name}", {a:#x}, {len(old)}, {blob(old)}, 0, {soft}, {doff}, {blob(bytes(new[k] for k in ks))}, {len(ks)}}},')
        else:
            rows.append(f'    {{"{name}", {a:#x}, {len(old)}, {blob(old)}, {blob(new) if new is not None else "0"}, {soft}, 0, 0, 0}},')
    out.append("static const struct cp_site cp_sites[] = {\n" + "\n".join(rows) + "\n};")
    # ---- main-processor sites: the encoder side (hard)
    lmr, avr, av_hi = [], [], 0
    for p in fl["patches"]:
        o, old, new = int(p["file_off"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        src = lm if p["binary"] == "libmpr.so" else av
        assert src[o:o + len(old)] == old
        (lmr if p["binary"] == "libmpr.so" else avr).append(f"    {{{o:#x}UL, {len(old)}, {blob(old)}, {blob(new)}}},")
        if p["binary"] == "av-cam.bin":
            av_hi = max(av_hi, o + len(old))
    out.append("static const struct mp_site lm_sites[] = {\n" + "\n".join(lmr) + "\n};")
    out.append("static const struct mp_site av_sites[] = {\n" + "\n".join(avr) + "\n};")
    spans = [(int(p["file_off"], 16), len(p["old"]) // 2) for p in fl["patches"] if p["binary"] == "av-cam.bin"]
    free = lambda k: all(DESC + DSIZE * (k + 4) <= so or so + sn <= DESC + DSIZE * k for so, sn in spans)
    d0 = next(k for k in range(NDESC - 4) if free(k))
    guards = (("unit_rows_0_2", UNIT, 0x30), ("clip_rows_2_7", CLIP + 0x20, 0x60), (f"descriptors_{d0}_{d0 + 3}", DESC + DSIZE * d0, 4 * DSIZE))
    rows = []
    for name, o, n in guards:
        assert all(o + n <= so or so + sn <= o for so, sn in spans), name
        rows.append(f'    {{"{name}", {o:#x}UL, {n}, {c_bytes(hashlib.sha256(av[o:o + n]).digest())}}},')
        av_hi = max(av_hi, o + n)
    out.append("static const struct av_guard av_guards[] = {\n" + "\n".join(rows) + "\n};")
    av_lo = min([so for so, _ in spans] + [o for _, o, _ in guards]) & ~0xFFF
    out.append(f"#define AV_LO {av_lo:#x}UL\n#define AV_HI {av_hi:#x}UL")
    # the dump's display pages: every page holding a screen site or guard
    disp_pages = sorted({int(x["ram_address"], 16) & ~0xFFF for x in sc["sites"] + sc["guards"]})
    dump_ranges = list(DUMP_FIXED) + [(f"display{k}", p, 1) for k, p in enumerate(disp_pages) if not any(a <= p < a + 4096 * n for _, a, n in DUMP_FIXED)]
    rows = [f'    {{"{n}", {a:#x}, {k}}},' for n, a, k in dump_ranges]
    assert all(CP_LO <= a and a + 4096 * k <= CP_HI for _, a, k in dump_ranges)
    starts = sorted((a, a + 4096 * k) for _, a, k in dump_ranges)
    assert all(e <= s for (_, e), (s, _) in zip(starts, starts[1:])), "two dump ranges overlap"
    out.append("#if DUMP\nstatic const struct dump_range dump_ranges[] = {\n" + "\n".join(rows) + "\n};\n#endif")
    text = ("/* Generated by gen_a1m2.py from the A1 II 4.00 files and the port designs. Do not edit. */\n#ifndef DUMP\n#define DUMP 0\n#endif\n"
            + "\n".join(blobs) + "\n" + "\n".join(out) + "\n")
    (HERE / "a1m2_expected.h").write_text(text, encoding="utf8", newline="\n")
    facts = {"label": LABEL, "cp_lo": CP_LO, "cp_hi": CP_HI, "avcam_phys": AVCAM_PHYS, "avcam_reserve": AVCAM_RESERVE,
             "id_files": {n: hashlib.sha256((EX / p).read_bytes()).hexdigest() for n, p in ID_FILES.items()},
             "id_pages": {hex(a): hashlib.sha256(cp[a - BASE:a - BASE + 4096]).hexdigest() for a in ID_PAGES},
             "cp_sites": [{"name": n, "address": hex(a), "length": len(o), "soft": s} for n, a, o, _, s in sites],
             "lm_sites": len(lmr), "av_sites": len(avr), "av_guards": [g[0] for g in guards], "dump_ranges": [[n, hex(a), k] for n, a, k in dump_ranges],
             "designs": {d["design"]: hashlib.sha256((DES / (d["design"] + ".json")).read_bytes()).hexdigest() for d in (og, oz, fl, sc, rr)}}
    (HERE / "a1m2_expected.json").write_text(json.dumps(facts, indent=1) + "\n", encoding="utf8", newline="\n")
    # ---- what the PC needs to read a dump without the firmware files
    matrix = []
    for k in range(MATRIX_ROWS):
        a = struct.unpack_from("<I", cp, MATRIX - BASE + MROW * k)[0]
        assert 0x1302000 <= a < 0x1303000
        matrix.append([a, cp[MATRIX - BASE + MROW * k + 4:MATRIX - BASE + MROW * k + MROW].hex()])
    assert not any(cp[MATRIX - BASE + MROW * MATRIX_ROWS:MATRIX - BASE + MROW * (MATRIX_ROWS + 1)]) and MATRIX + MROW * (MATRIX_ROWS + 1) == COLMAP
    shadow0 = min(a for a, _ in matrix)
    emu = json.loads((ROOT / "evidence/a1m2/drvparam_stock_a1m2_400.json").read_text(encoding="utf8"))["modes"]
    ref = {"about": "A1 II 4.00 reference data for reading an a1m2read dump; from cpapp-b.bin and build/emu_drvparam.py a1m2_400", "matrix_address": hex(MATRIX),
           "matrix_row_bytes": MROW, "matrix_columns": 28, "matrix": matrix, "column_map": list(struct.unpack_from("<%dI" % NMODES, cp, COLMAP - BASE)),
           "mode_ids": [hex(x) for x in ids], "records_address": hex(RECS), "record_size": REC, "shadow_first": hex(shadow0),
           "emulated_stock_records": {m: v["record"] for m, v in emu.items()}, "size_table_address": hex(SIZE_TABLE),
           "stored_records_design": og["stored_records"], "stored_records_design_real_rows": rr["stored_records"], "open_gate_column": 2,
           "window_cells": {"start_block": {"row": 8, "shadow_offset": "0x20", "stock": 6, "open_gate": 1},
                            "half_height": {"row": 9, "shadow_offset": "0x24", "stock": 25, "open_gate": 30},
                            "reg_0x90": {"row": 18, "shadow_offset": "0x90", "stock": 58, "open_gate": 63}},
           "window": {"stock_height": 2430, "design_height": og["summary"]["window"][1],
                      "record_offsets": {"height": "0x66", "pdaf_rows": "0x8c", "lc4": "0xfe", "band": "0x10a", "readout_length": "0x148",
                                         "lc6": "0x16a", "sampling_ratio": "0x4"}},
           "screen_words": [{"address": s["ram_address"], "stock": s["old"], "new": s["new"], "note": s.get("note", "")} for s in sc["sites"]],
           "screen_design": sc["design"],
           "panel_type": {"rear": hex(PANEL_REAR), "evf": hex(PANEL_EVF), "codes": {"1": "16:9", "2": "4:3", "3": "3:2"}},
           "c3_ratio_constants": {"addresses": ["0x1fafa4", "0x1fafa8"], "note": "the letterbox constants the C3 routine writes per state (A1M2_PORT_SCREEN.md)"},
           "ram": {"resize_state_weak": "0x194f054 / 0x194f130 / 0x1950b14 (port_addr from the FX2's, 1-2 votes)", "resize_work_weak": "0x1626cb8",
                   "sensor_object": "0x1790350", "drive_parameter_pointer": "control +0x6cc"}}
    assert len(ref["emulated_stock_records"]) == NMODES
    (HERE / "a1m2_reference.json").write_text(json.dumps(ref) + "\n", encoding="utf8", newline="\n")
    print(f"a1m2_expected.h: {len(sites)} coprocessor sites ({len(sc['sites'])} of the screen, 4 stored records), "
          f"{len(lmr)} libmpr sites, {len(avr)} av-cam sites, {len(dump_ranges)} dump ranges, {len(text)} bytes of header")


if __name__ == "__main__":
    main()
