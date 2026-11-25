"""A1 II 4.00 (a1m2_400) coprocessor RAM words of the open-gate kit's memory/size side (A1 II port, 2026-11-26).

  C:/Python313/python.exe -B build/build_ram_words_a1m2.py
        writes modding/designs/outsz2560_a1m2_v1.json (+ _pokes_ram.txt) and evidence/a1m2/dmm/raw_write_buffer_a1m2.json
  C:/Python313/python.exe -B build/build_ram_words_a1m2.py --dmmwb ROWS --pitch BYTES [--name dmmwb_a1m2_v1] [--write] [--force]
        a taller movie raw write buffer (memory id 0x43e) for a first stage of ROWS rows of BYTES per line: checked in the A1 II's own
        DMM allocator; writes modding/designs/<name>.json only with --write. Refuses when the stock unit already holds the stage (not
        needed) unless --force, and when the size does not fit the layouts in place (largest in-place unit: 23,420,928 bytes).

1. Output size `outsz2560_a1m2_v1` (the A7 IV's working outsz2560_v1, as ported to the A7C II / FX2):
  - The movie size table is filled at run time by 0x501834 = the FX2's 0x4ff894 (match_seed 64 votes; diff_consts 305 of 342 aligned: relocated
    targets, base 0x18f6028 -> 0x1938404, its second settings block 0x196aa58 -> 0x19acc14, every field from +0x88 on 4 bytes lower), 0x412 bytes
    to its pop at 0x501c44. build/emu_size_table.py a1m2_400 runs it alone: table at base + 0x84 = 0x1938488, its 16 entries equal the FX2's
    (and the A7C II's): 8K classes with memory ids 0x49e / 0x43f, 3840 x 2160 entries 0x43e / 0x2d9 at 0x19384c8 / 0x19384d0.
  - The reader 0x5214fe (tbh on the request's size class [r5 + 0x9c], bound 12; = FX2 0x51fca6, match_seed 29 votes) loads base + 0xcc =
    0x19384d0 in case 3 (UHD). Decoded from the file below; cases 0..5 pick the same entries as the FX2's.
  - The output buffer of that entry, memory id 0x2d9, is 11 units of 13,271,040 bytes on the A1 II (9 on the A7 IV / FX2); a 3840 x 2560
    picture at format code 2 (x 1.25 bytes per pixel, read on the A7 IV camera; the A1 II's picture-bytes function 0x520678 has the same
    switch) is 12,288,000 bytes. At code 3 it would be 14,745,600 and would not fit.
  Guards: the entry before (3840, 2160, memory id 0x43e) and this entry's memory id (0x2d9). Old/new/guard bytes equal the A7 IV's design.

2. Movie raw write buffer (memory id 0x43e, DMM key 0x57f): NOT a size problem for the FF 4K mode at full height.
  - A1 II units: seven of 21,410,048 bytes, in two layouts of a 106,954,752-byte parent (key 0x38): group 0x8c (0x635 + four 0x57f,
    8,043,520 left) and group 0x8e (0x635 + three 0x57f + 0x6b3, 8,043,520 left), both limit 1. The 8K buffer id 0x49e (key 0x616) is two
    units of 42,128,640 = 8640 x 4876 in group 0x8d: exactly the 8K stage (8640 wide, 4876 rows).
  - The refusal check is the A7 IV's: port set-up 0x26b9a0 (= ZV-E1 0x2613a8, match_thumb exact; text 'CamCore: AIF%d out[0x%x] >
    memsize[0x%x]' at 0x1026aa6), out = ((skip + 1) x (rows - 1) + 1) x line bytes, refused when out > the extent; called only by the
    wrapper 0x7d56f0 (= A7 IV 0x6cef98: formats 0x11 and 6 pack two lines).
  - The record selector (build/emu_record_selector.py a1m2_400) gives 0x8c0 and 0x820 the pair 0xdf6844 / 0xdf73fc: stage 2446 rows
    (active 2430), half width 2220, first scaler 1:1 (2208 / 2176 -> 2204 / 2172 x 2446); the stream-0 window of 0x8c0 is 4320 x 2430,
    i.e. a 2 x 2 binned full-width read-out (8K 0x2c0: 8640 x 4860; stills 0xa000: 8640 x 5760). 0x8c1 / 0x821 (stream-0 window
    5760 x 3240 from x 1476: the Super 35 crop) get 0xdf7fb4 / 0xdf8b6c, stage 3264, half 2944.
  - Line bytes: on the A7 IV the unit is exactly 2 x half x stage (2 x 3520 x 3958 = 27,864,320, the read-out 7032 rounded up); on the A1 II
    the 8K unit is exactly read-out width x stage (8640 x 4876). Both rules put the FF 4K line at 4320..4440 bytes, so the unit holds
    4,822 rows (4440) to 4,956 rows (4320): far more than a full-height binned stage (2880 active rows, about 2,896 with the margins:
    12,858,240 bytes at 4440). No change is needed for that design.
  - For a design that keeps a wider line (the Super 35 / 2/3-type line of 5,888 bytes holds 3,636 rows; the 8K line of 8,640 bytes holds
    2,478 rows in a 0x43e unit), `--dmmwb ROWS --pitch BYTES` raises the seven records in place (groups 0x8c and 0x8e keep their other
    units); the largest unit both layouts still take is 23,420,928 bytes (group 0x8c: 13,271,040 + 4 x S <= 106,954,752).
Design only; nothing has run on an A1 II.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import emu_dmm_server as E  # noqa: E402
import emu_size_table  # noqa: E402
import find_movw  # noqa: E402
import locate_file  # noqa: E402
import parse_dmmcfg as P  # noqa: E402

B = 0x108000
BUILD, NAME = "a1m2_400", "outsz2560_a1m2_v1"
IMG = locate_file.locate(BUILD, "cpapp-b.bin").read_bytes()
SHA = hashlib.sha256(IMG).hexdigest()
# (switch address of the tbh, its bound, the base register value, the offset case 3 loads)
READERS = {"a1m2_400": (0x5214FE, 0xC, 0x1938404, 0xCC), "fx2_101": (0x51FCA6, 0xC, 0x18F6028, 0xD0)}
KEY, PARENT, OUT_ID, RAW_ID = 0x57F, 0x38, 0x2D9, 0x43E
RAW_GROUPS = (0x8C, 0x8E)
STOCK_UNIT = 21410048
EVID = ROOT / "evidence/a1m2/dmm"


def image(build):
    return IMG if build == BUILD else locate_file.locate(build, "cpapp-b.bin").read_bytes()


def case_load(build, case):
    """Decode the reader's tbh switch from the file: the address it jumps to for `case`, and the base and offset that case loads."""
    sw, bound, base, _ = READERS[build]
    img = image(build)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    pre = list(md.disasm(img[sw - 4 - B:sw + 4 - B], sw - 4))          # cmp r0, #bound (16-bit); bhi (16-bit); tbh
    assert [i.mnemonic for i in pre] == ["cmp", "bhi", "tbh"] and pre[0].op_str.endswith("#%#x" % bound), pre
    entries = struct.unpack_from("<%dH" % (bound + 1), img, sw + 4 - B)
    target = sw + 4 + 2 * entries[case]
    ins = list(md.disasm(img[target - B:target + 12 - B], target))[:3]
    assert [i.mnemonic for i in ins][:2] == ["movw", "movt"] and ins[2].mnemonic in ("ldr", "ldr.w"), ins
    lo, hi = int(ins[0].op_str.split("#")[1], 0), int(ins[1].op_str.split("#")[1], 0)
    off = int(ins[2].op_str.split("#")[1].rstrip("]"), 0)
    assert (hi << 16 | lo) == base, (build, hex(hi << 16 | lo))
    return target, base, off


def loads_of(base, off):
    """Every MOVW/MOVT build of `base` in the image followed within six instructions by a load at [reg, #off]."""
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    hits = []
    names = {"r9": "sb", "r10": "sl", "r11": "fp", "r12": "ip", "r13": "sp", "r14": "lr"}
    for val, addr, reg in find_movw.pairs(IMG, base, base + 1, code_end=B + len(IMG)):
        reg = str(reg)
        reg = names.get(reg, reg) if reg.startswith("r") else names.get("r%d" % int(reg), "r%d" % int(reg))
        for i in list(md.disasm(IMG[addr - B:addr + 32 - B], addr))[:8]:
            if i.mnemonic.startswith("ldr") and i.op_str.endswith("[%s, #%#x]" % (reg, off)):
                hits.append(hex(i.address))
    return sorted(set(hits))


def outsz():
    t, rows, writes = emu_size_table.table(BUILD)
    t_f, rows_f, _ = emu_size_table.table("fx2_101")
    assert t == 0x1938488 and rows == rows_f, "the A1 II's table differs from the FX2's"
    assert rows[8] == (3840, 2160, RAW_ID) and rows[9] == (3840, 2160, OUT_ID)
    site = t + 8 * 9
    tgt, base, off = case_load(BUILD, 3)
    tgt_f, base_f, off_f = case_load("fx2_101", 3)
    assert base + off == site and base_f + off_f == 0x18F60F8 == t_f + 8 * 9, "case 3 does not load the second 3840 x 2160 entry"
    others = {c: case_load(BUILD, c)[2] for c in range(6)}
    others_f = {c: case_load("fx2_101", c)[2] for c in range(6)}
    assert all(base + others[c] - t == base_f + others_f[c] - t_f for c in range(6)), "the two switches pick different entries"
    readers = loads_of(base, off)
    cfg = P.Config(P.find_file(BUILD), BUILD)
    out_units = sorted(u["size"] for k in cfg.id_rows[OUT_ID]["keys"] for u in cfg.units_by_key[k])
    assert out_units == [13271040] * 11 and 3840 * 2560 * 5 // 4 <= out_units[0] < 3840 * 2560 * 3 // 2
    ref = json.loads((ROOT / "modding/designs/outsz2560_v1.json").read_text(encoding="utf8"))
    ref_f = json.loads((ROOT / "modding/designs/outsz2560_fx2_v1.json").read_text(encoding="utf8"))
    sites = [{"ram_address": hex(site), "old": struct.pack("<HH", 3840, 2160).hex(), "new": struct.pack("<HH", 3840, 2560).hex(),
              "note": "the second 3840x2160 entry (output width and height; class 4 of the A1 II's table as the emulator counts it, the A7 IV's "
                      "class 3) [A7 IV 0x143c7bc, A7C II 0x1a531c8, FX2 0x18f60f8]"}]
    guards = [{"ram_address": hex(site - 8), "bytes": struct.pack("<HHI", 3840, 2160, RAW_ID).hex(),
               "note": "the entry before: 3840, 2160, memory id 0x43e [A7 IV 0x143c7b4, FX2 0x18f60f0]"},
              {"ram_address": hex(site + 4), "bytes": struct.pack("<I", OUT_ID).hex(), "note": "this entry's memory id, 0x2d9 [A7 IV 0x143c7c0, FX2 0x18f60fc]"}]
    for mine, theirs in ((sites, ref["sites"]), (guards, ref["guards"]), (sites, ref_f["sites"]), (guards, ref_f["guards"])):
        assert [(x.get("old"), x.get("new"), x.get("bytes")) for x in mine] == [(x.get("old"), x.get("new"), x.get("bytes")) for x in theirs]
    res = {"design": NAME, "build": BUILD, "camera": "ILCE-1M2 (A1 II), firmware 4.00",
           "title": "Output size of the stock 4K size class: 3840x2160 to 3840x2560, in the coprocessor's movie size table (RAM) (A1 II 4.00 port)",
           "kind": "ram_words", "artifact": "cpapp-b.bin, RAM only: these bytes are not in the file",
           "emulated_image_sha256": SHA,
           "generated_by": "build/build_ram_words_a1m2.py", "ported_from": {"design": "outsz2560_v1", "build": "a7iv_602", "also_as": "outsz2560_fx2_v1 (fx2_101), outsz2560_c2_v1 (a7c2_201)"},
           "status": "addresses from emulating and reading the A1 II's own code; never read or written on an A1 II. The same word change (outsz2560_v1) "
                     "works on the A7 IV (requests 26 to 29, F688, F698, F700)",
           "table": f"movie size table {t:#x} (base {base:#x} + 0x84; 0x501834 fills it; the reader 0x5214fe, case 3, loads base + {off:#x} = {site:#x})",
           "summary": dict(ref["summary"], goes_with=["the A1 II sensor-side design", "the A1 II encoder-side design (3840 x 2560)"]),
           "emulated": {"function": "0x501834", "bytes": 0x412, "base": hex(base), "table": hex(t), "stores_into_block": len(writes),
                        "entries_equal_fx2_101": True, "entries": [[w, h, hex(m)] for w, h, m in rows],
                        "reader": {"switch": hex(READERS[BUILD][0]), "case_3_code": hex(tgt), "case_3_loads": hex(base + off),
                                   "cases_0_to_5_entry_offsets": [hex(base + others[c] - t) for c in range(6)],
                                   "fx2_101_switch": hex(READERS["fx2_101"][0]), "fx2_101_case_3_loads": hex(base_f + off_f),
                                   "every_load_of_base_plus_0xcc": readers},
                        "output_buffer_id_0x2d9_units": out_units},
           "sites": sites, "guards": guards,
           "precondition": "none of its own: the table is read when a movie request is set up; write it with the camera in stills, as on the A7 IV",
           "restore": "write the old word back, or cold boot (the set-up fills the table again at start-up)",
           "checked_against": ["build/emu_size_table.py a1m2_400 (the A1 II's set-up run alone; entries equal the FX2's)",
                               "the tbh switches of the A1 II (0x5214fe) and FX2 (0x51fca6) readers, decoded from the files: cases 0 to 5 pick the same entries",
                               "the A1 II's DmmCfg.bin: id 0x2d9 = 11 x 13,271,040 bytes"],
           "not_shown": ["anything on an A1 II",
                         "the A1 II's format code in 4K (2 on the A7 IV camera, request 25; at code 3 a 3840x2560 picture would need 14,745,600 bytes, "
                         "more than the 13,271,040-byte unit)",
                         "what the settings block 0x19acc14 holds on a camera (the emulation runs the set-up with it zero; the A1 II's head stores 1 "
                         "where the FX2's stores 0 at 0x501894, before the entries)"]}
    dd = ROOT / "modding/designs"
    (dd / f"{NAME}.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf8", newline="\n")
    (dd / f"{NAME}_pokes_ram.txt").write_text("".join(f"{x['ram_address']} {x['new']}\n" for x in sites), encoding="utf8", newline="\n")
    print(f"{NAME}: site {site:#x} {sites[0]['old']} -> {sites[0]['new']}; guards {[g['ram_address'] for g in guards]}; table {t:#x} = FX2's; "
          f"reader case 3 at {tgt:#x} loads {base + off:#x} (FX2 {base_f + off_f:#x}); loads of base+{off:#x}: {readers}")
    return res


# ------------------------------------------------------------------ the raw write buffer

def raw_units(cfg):
    us = [u for u in cfg.units_by_key[KEY]]
    assert sorted(u["group"]["gid"] for u in us) == [0x8C] * 4 + [0x8E] * 3 and all(u["size"] == STOCK_UNIT for u in us)
    return us


def max_in_place(cfg):
    """The largest unit size (multiple of 128) for which both layouts still fit their parent, from the layouts' own arithmetic."""
    parent = min(cfg.parent_sizes(PARENT))
    best = None
    for s in range(STOCK_UNIT, parent, 128):
        ok = True
        for g in (g for g in cfg.groups if g["gid"] in RAW_GROUPS):
            run = 0
            for u in g["units"]:
                a = cfg.align(u["type"])
                run = ((run + a - 1) & -a if a else run) + (s if u["key"] == KEY else u["size"])
            ok &= run <= parent
        if not ok:
            break
        best = s
    return best, parent


def server(cfg, size=None):
    s = E.Server(cfg.data, cfg)
    assert s.init() == 0 and s.cur == len(cfg.data) and not s.fatal
    words = []
    if size:
        for gid in RAW_GROUPS:
            words += s.set_size(KEY, gid, size)
    return s, words


def opens_check(cfg, size):
    """Seven opens of 0x43e, then 0x4b8 and 0x4b7, an eighth 0x43e, then free everything: the A1 II's own allocator."""
    s, words = server(cfg, size)
    out = [s.open(RAW_ID) for _ in range(7)] + [s.open(0x4B8), s.open(0x4B7), s.open(RAW_ID)]
    want = size or STOCK_UNIT
    assert all(o["ok"] and [x["size"] for x in o["extents"]] == [want] for o in out[:7]), "an open of 0x43e did not return the expected size"
    assert out[7]["ok"] and out[7]["extents"][0]["size"] == 13271040 and out[8]["ok"] and out[8]["extents"][0]["size"] == 3317760, "0x4b8 / 0x4b7 no longer open"
    assert not out[9]["ok"], "an eighth write buffer was expected to be refused"
    spans = sorted((int(x["address"], 16), int(x["address"], 16) + x["size"]) for o in out if o["ok"] for x in o["extents"])
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), "opened units overlap"
    bases = sorted(cfg.bases(PARENT))
    parent = min(cfg.parent_sizes(PARENT))
    assert all(any(b <= lo and hi <= b + parent for b in bases) for lo, hi in spans), "a unit lies outside its parent"
    frees = [s.free(n) for n in range(9)]
    assert all(f["ok"] for f in frees) and not s.fatal
    assert not [o for o in s.objects() if o["in_use"]], "something stayed in use after the frees"
    return {"opens_of_0x43e": [o["extents"][0] for o in out[:7]], "open_0x4b8": out[7]["extents"], "open_0x4b7": out[8]["extents"],
            "eighth_open_of_0x43e": out[9]["result"], "all_inside_a_parent_and_disjoint": True, "all_freed": True}, words


def raw_report(cfg):
    us = raw_units(cfg)
    s_max, parent = max_in_place(cfg)
    stock = opens_check(cfg, None)[0]
    lines = {"FF 4K 0x8c0 (2 x half 2220, A7 IV rule)": 4440, "FF 4K 0x8c0 (read-out 4320, A1 II 8K rule)": 4320,
             "Super 35 0x8c1 / a 2/3-sampled 5.8K line (2 x half 2944)": 5888, "8K line (8640)": 8640}
    cap = {k: {"line_bytes": v, "rows_in_a_stock_unit": STOCK_UNIT // v, "rows_in_the_largest_in_place_unit": s_max // v} for k, v in lines.items()}
    need_ff = 4440 * (2880 + 16)
    rep = {"about": "The A1 II 4.00 movie raw write buffer (memory id 0x43e) against a full-height first stage (A1 II port, build/build_ram_words_a1m2.py; "
                    "see its header). Static plus the DMM server's own code in Unicorn.",
           "units": {"id": "0x43e", "key": hex(KEY), "size": STOCK_UNIT, "count": len(us), "parent_key": hex(PARENT), "parent_size": parent,
                     "layouts": {"0x8c": "0x635 (13,271,040) + four 0x57f, 8,043,520 left, limit 1", "0x8e": "0x635 + three 0x57f + 0x6b3 (21,410,048), 8,043,520 left, limit 1"},
                     "records_file_offsets": [hex(u["at"]) for u in us], "records_ram": [hex(cfg.ram("unit_records", u["seq"] * 0x14)) for u in us],
                     "size_fields_ram": [hex(cfg.ram("unit_records", u["seq"] * 0x14) + 12) for u in us]},
           "eight_k_buffer": {"id": "0x49e", "key": "0x616", "units": "2 x 42,128,640 = 8640 x 4876 (the 8K stage exactly), group 0x8d"},
           "refusal_check": {"port_setup": "0x26b9a0 (= ZV-E1 0x2613a8, match_thumb exact)", "text": "0x1026aa6 'CamCore: AIF%d out[0x%x] > memsize[0x%x]'",
                             "rule": "out = ((skip + 1) x (rows - 1) + 1) x line bytes > extent size -> refused, logged, no error", "wrapper": "0x7d56f0 (only caller; = A7 IV 0x6cef98)"},
           "records": {"0x8c0 / 0x820": {"pair": ["0xdf6844", "0xdf73fc"], "stage_rows": 2446, "active_rows": 2430, "half_width": 2220, "stream0_window": "4320 x 2430"},
                       "0x8c1 / 0x821": {"pair": ["0xdf7fb4", "0xdf8b6c"], "stage_rows": 3264, "active_rows": 3240, "half_width": 2944, "stream0_window": "5760 x 3240 from x 1476 (Super 35 crop)"},
                       "0x2c0 / 0x280 (8K)": {"pair": ["0xdf3964", "0xdf451c"], "stage_rows": 4876, "active_rows": 4860, "half_width": 4364, "stream0_window": "8640 x 4860"}},
           "capacity": cap, "largest_in_place_unit": s_max,
           "verdict": f"no change needed for a full-height FF 4K stage at the 0x8c0 sampling: about 2,896 rows x 4,440 = {need_ff:,} bytes <= {STOCK_UNIT:,}",
           "stock_allocator_run": stock}
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "raw_write_buffer_a1m2.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"raw write buffer: 7 x {STOCK_UNIT:,} (key 0x57f, groups 0x8c/0x8e of parent 0x38 {parent:,}); largest in-place unit {s_max:,}")
    for k, v in cap.items():
        print(f"  {k}: {v['rows_in_a_stock_unit']} rows (stock unit), {v['rows_in_the_largest_in_place_unit']} rows (largest in place)")
    print("  " + rep["verdict"])
    print("  stock allocator: 7 opens of 0x43e ok, eighth:", stock["eighth_open_of_0x43e"])
    return rep


def dmmwb(cfg, rows, pitch, name, write, force):
    size = (pitch * rows + 127) & ~127
    s_max, parent = max_in_place(cfg)
    if size <= STOCK_UNIT and not force:
        raise SystemExit(f"not needed: {rows} rows x {pitch} bytes = {pitch * rows:,} fits the stock unit of {STOCK_UNIT:,} (--force to build anyway)")
    if size > s_max:
        raise SystemExit(f"{size:,} bytes does not fit the layouts in place (largest {s_max:,}); a larger buffer needs another layout")
    run, words = opens_check(cfg, size)
    us = raw_units(cfg)
    sites = []
    for u in us:
        a = cfg.ram("unit_records", u["seq"] * 0x14) + 12
        sites.append({"ram_address": hex(a), "what": f"size of a key {KEY:#x} record of group {u['group']['gid']:#x}", "file_offset_of_the_same_field": hex(u["at"] + 12),
                      "old": struct.pack("<I", u["size"]).hex(), "new": struct.pack("<I", size).hex(), "old_value": u["size"], "new_value": size})
    assert sorted(w["ram_address"] for w in words) == sorted(st["ram_address"] for st in sites), "the harness wrote other words than the design's"
    design = {"design": name, "build": BUILD,
              "title": f"Memory-only DMM change: the movie raw write buffer (memory id 0x43e) grows from 21,410,048 to {size:,} bytes ({rows} rows of {pitch} bytes) (A1 II 4.00)",
              "artifact": "coprocessor RAM (the DMM server's copy of /cp/DmmCfg.bin); no file is changed",
              "generated_by": f"build/build_ram_words_a1m2.py --dmmwb {rows} --pitch {pitch} --name {name}",
              "summary": {"sites": len(sites), "bytes": 4 * len(sites), "rows": rows, "line_bytes": pitch, "unit_size": size, "stock_unit_size": STOCK_UNIT,
                          "parent_key": hex(PARENT), "parent_size": parent, "largest_in_place_unit": s_max,
                          "cache_lines_64": sorted({hex(int(st["ram_address"], 16) & ~63) for st in sites})},
              "precondition": "no unit object of key 0x57f, 0x634, 0x635 or 0x6b3 exists when the words are written (every 0x38 parent undivided): "
                              "an existing division keeps its old units",
              "restore": "write the old words back while the same precondition holds, or cold boot",
              "checked_in_the_firmware_allocator": dict(run, tool="build/emu_dmm_server.py --build a1m2_400 (the A1 II's own DMM code)"),
              "not_shown": ["anything on an A1 II", "the line bytes of the stage on a camera"],
              "sites": sites}
    print(f"{name}: {len(sites)} sites, unit {size:,} bytes ({rows} rows x {pitch}); largest in place {s_max:,}; allocator: 7 opens ok, eighth {run['eighth_open_of_0x43e']}")
    if write:
        d = ROOT / "modding/designs"
        (d / f"{name}.json").write_text(json.dumps(design, indent=1) + "\n", encoding="utf8", newline="\n")
        (d / f"{name}_pokes_ram.txt").write_text("".join(f"{st['ram_address']} {st['new']}\n" for st in sites), encoding="ascii", newline="\n")
        print(f"wrote modding/designs/{name}.json")
    return design


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dmmwb", type=int, metavar="ROWS")
    ap.add_argument("--pitch", type=int, default=4440)
    ap.add_argument("--name", default="dmmwb_a1m2_v1")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    E.use_build(BUILD)
    cfg = P.Config(P.find_file(BUILD), BUILD)
    if a.dmmwb:
        dmmwb(cfg, a.dmmwb, a.pitch, a.name, a.write, a.force)
        return
    outsz()
    raw_report(cfg)


if __name__ == "__main__":
    main()
