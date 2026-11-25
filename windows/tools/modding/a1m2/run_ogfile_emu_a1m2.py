"""A1 II 4.00: function-level emulation of the encoder-side designs of the A1 II kit, stock against changed, in the A1 II's own av-cam.bin and
libmpr.so (2026-11-26, modding/A1M2_PORT_ENCODER.md). The changes are applied in emulated memory only. Nothing here is hardware.

  ogfile2560_hs_s_a1m2_v1 / _v2   (build/build_ogfile.py --build a1m2_400 [--meta]): XAVC HS 4K + XAVC S 4K at 3840x2560, 23.98p / 25p
  ogfilesi2560_a1m2_v1            (build/build_ogfile_si.py --build a1m2_400): XAVC S-I 4K at 3840x2560, one more step on top of _v2

The A1 II's av-cam functions are mostly NOT the A7 IV's bodies (build/avcam_fnport.py finds only the allocator and the log call); they were found
by their table references and read instruction by instruction against the A7 IV's (modding/A1M2_PORT_ENCODER.md):
  matcher           0x234acc   the A7 IV's 0x21b780 logic, same request offsets; scans 0x2ae = 686 descriptors from index 0 (A7 IV from 3)
  memory function   0x22c9e8   the A7 IV's 0x2136c4 logic and thresholds, same context offsets; one difference: a CD id of 0 is skipped
                               (cbz at 0x22cb80), where the A7 IV asks the allocator for id 0 and fails
  clip format       0x1a4134   (context, request) with raster at request +0x68/+0x6a and kind byte +0x81, as the FX2's 0x1a2670
  start block       0x2307fc   called at 0x22e528 after the A7 IV's six instructions (0x2151d4); run as the A1 II's own
  helpers           allocator 0x23c564 (= A7 IV 0x222bd0), log 0x28c264 (= 0x27278c) / 0x28c224, memcpy 0x28c780, memset 0x28c798
  tables            descriptors 0x3ab2d4, unit types 0x3ab234, profiles 0x3c34b4 / 0x3da8b4, clip 0x3a9158, frame rates 0x343f30
  codec firmware    vcd_firmware_imola2.bin is the A7 IV's file byte for byte (asserted): the memory need is build/emu_vcd_chmem.py's
  libmpr.so         g_videoParamComb 0x2d2ca8; MP4 writer = the A7 IV's moved by +0x15c4 (build/emu_mp4_meta.py's Lib with FUNCS["a1m2_400"])

Run with the Python that has Unicorn:  C:\\Python313\\python.exe -B build/run_ogfile_emu_a1m2.py
Writes evidence/a1m2/encoder/ogfile_emu_a1m2.json; exits 1 if a check fails.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import emu_mp4_meta  # noqa: E402
import emu_vcd_chmem as V  # noqa: E402
import locate_file  # noqa: E402
import parse_dmmcfg  # noqa: E402
import run_ogfile_emu as E  # noqa: E402

AVB = E.AVB
BUILD = "a1m2_400"
DESC, NDESC, UNIT, FPS, CLIPT = 0x3AB2D4, 686, 0x3AB234, 0x343F30, 0x3A9158
PROFILES = ((0x3C34B4, 371), (0x3DA8B4, 315))
COMB = 0x2D2CA8
FN = {"DESC": AVB + DESC, "MATCH": AVB + 0x234ACC, "CLIPFN": AVB + 0x1A4134, "UNITFN": AVB + 0x22C9E8, "BUILDER": AVB + 0x2307FC,
      "DMM_OPEN": AVB + 0x23C564, "LOGF": AVB + 0x28C264, "LOGH": AVB + 0x28C224, "MEMSET": AVB + 0x28C798, "MEMCPY": AVB + 0x28C780}
V.DESC, V.NDESC, V.UNIT_TABLE, V.FPS_TABLE = AVB + DESC, NDESC, AVB + UNIT, AVB + FPS
D = ROOT / "modding" / "designs"
HS_S = ("ogfile2560_hs_s_a1m2_v1", "ogfile2560_hs_s_a1m2_v2")
SI, STEP4, STEP4_V1 = "ogfilesi2560_a1m2_v1", "ogfile2560_hs_s_a1m2_v2", "ogfile2560_hs_s_a1m2_v1"
W0, H0, W1, H1 = 3840, 2160, 3840, 2560
CLIP_4K = 23


def apply(img, *names, kind="avcam"):
    b = bytearray(img)
    for n in names:
        for off, nb in E.pokes(D / f"{n}_pokes_{kind}.txt"):
            b[off:off + len(nb)] = nb
    return bytes(b)


class Cam(E.AvCam):
    def __init__(self, img):
        super().__init__(img, FN)

    def clip(self, w, h):
        """The A1 II's clip-format function: x0 an object whose +8 leads to a record read only on the failure path, x1 the request."""
        self.uc.mem_write(E.CTX, struct.pack("<QQ", 0, E.CTX + 0x40) + bytes(0x30) + struct.pack("<Q", E.CTX + 0x80) + bytes(0x40))
        req = bytearray(0x100)
        struct.pack_into("<HH", req, 0x68, w, h)
        req[0x81] = 1
        self.uc.mem_write(E.REQ, bytes(req))
        return self.call(self.fn["CLIPFN"], E.CTX, E.REQ) & 0xFFFFFFFF


def find_functions(a7, a1):
    """Assert the facts the docstring relies on (the parts that can be checked by bytes)."""
    import avcam_fnport
    got = avcam_fnport.port(BUILD, [0x222BD0, 0x27278C], a7, a1)
    assert {k: v[0] for k, v in got.items()} == {0x222BD0: 0x23C564, 0x27278C: 0x28C264}, got
    seq = struct.unpack_from("<6I", a7, 0x2151D4)
    sites = [x for x in range(0x200000, 0x260000, 4) if struct.unpack_from("<6I", a1, x) == seq]
    assert sites == [0x22E510], sites
    w = struct.unpack_from("<I", a1, 0x22E528)[0]
    assert w & 0xFC000000 == 0x94000000 and 0x22E528 + 4 * ((w & 0x3FFFFFF) - ((w & 0x2000000) << 1)) == 0x2307FC
    tgt = lambda at, ws: at + 8 + 4 * ((ws[2] & 0x3FFFFFF) - ((ws[2] & 0x2000000) << 1))
    for a7_at, a1_at in ((0x272CA8, 0x28C780), (0x272CC0, 0x28C798)):
        wa, wb = struct.unpack_from("<6I", a7, a7_at), struct.unpack_from("<6I", a1, a1_at)
        assert wa[:2] == wb[:2] and wa[3:] == wb[3:] and tgt(a7_at, wa) == tgt(a1_at, wb), (hex(a7_at), hex(a1_at))
    # the matcher's descriptor count and table; the memory function's table and its CD-id-0 skip
    assert struct.unpack_from("<I", a1, 0x234D00)[0] == 0xF10AB81F            # cmp x0, #0x2ae
    adrp_add = lambda at: ((at & ~0xFFF) + ((((struct.unpack_from("<I", a1, at)[0] >> 5) & 0x7FFFF) << 2 | (struct.unpack_from("<I", a1, at)[0] >> 29) & 3) << 12)
                           + ((struct.unpack_from("<I", a1, at + 4)[0] >> 10) & 0xFFF))
    assert adrp_add(0x234BBC) == DESC and adrp_add(0x22CAD8) == UNIT and adrp_add(0x1A414C) == CLIPT and adrp_add(0x28A644) == FPS
    assert struct.unpack_from("<I", a1, 0x22CB80)[0] & 0xFF00001F == 0x34000016      # cbz w22 (the CD id), skipping the CD open
    assert locate_file.locate(BUILD, "vcd_firmware_imola2.bin").read_bytes() == locate_file.locate("a7iv_602", "vcd_firmware_imola2.bin").read_bytes()
    return {"matcher": "0x234acc", "memory_function": "0x22c9e8 (CD id 0 skipped at 0x22cb80)", "clip_format": "0x1a4134 (two-argument form)",
            "start_block": "0x2307fc (called at 0x22e528)", "allocator": "0x23c564 (= A7 IV 0x222bd0)", "log": "0x28c264 / 0x28c224",
            "memcpy_memset": "0x28c780 / 0x28c798", "codec_firmware": "the A7 IV's vcd_firmware_imola2.bin, byte for byte"}


def dmm_cfg():
    return parse_dmmcfg.Config(parse_dmmcfg.find_file(BUILD, "setting"), BUILD)


def id_units(cfg, i):
    return [u for k in cfg.id_rows.get(i, {}).get("keys", []) for u in cfg.units_by_key.get(k, [])]


def hs_s_checks(name, av, cfg):
    design = json.loads((D / f"{name}.json").read_text(encoding="utf8"))
    assert design["build"] == BUILD
    changed = apply(av, name)
    s, c = Cam(av), Cam(changed)
    res, checks = {"design": name, "format": design["format"]}, {}
    sel, ok = [], True
    for p in design["descriptors"]:
        k = p["descriptor"]
        d = s.desc(k)
        row = {"descriptor": k, "format": p["format"], "rate": p["rate"], "quality_class": p["quality_class"], "key": d["key"],
               "stock_3840x2160": s.select(d, W0, H0), "stock_3840x2560": s.select(d, W1, H1),
               "changed_3840x2560": c.select(d, W1, H1), "changed_3840x2160": c.select(d, W0, H0)}
        row["as_designed"] = row["stock_3840x2160"] == k and row["stock_3840x2560"] is None and row["changed_3840x2560"] == k and row["changed_3840x2160"] is None
        ok &= row["as_designed"]
        sel.append(row)
    untouched = []
    chg = {p["descriptor"] for p in design["descriptors"]}
    codecs = {s.desc(k)["codec"] for k in chg}
    for k in range(NDESC):
        d = s.desc(k)
        if d["infr"] or k in chg:
            continue
        if ((d["w"], d["h"]) == (W0, H0) and d["codec"] in codecs and d["codfr"] in (0, 1, 2)) or ((d["w"], d["h"]) == (7680, 4320) and d["codec"] in (4, 0xE)):
            a, b = s.select(d, d["w"], d["h"]), c.select(d, d["w"], d["h"])
            untouched.append({"descriptor": k, "raster": [d["w"], d["h"]], "codec": hex(d["codec"]), "coding_rate_code": d["codfr"], "stock": a, "changed": b,
                              "changed_3840x2560": c.select(d, W1, H1)})
    checks["matcher: every changed descriptor found at 3840x2560 only (stock at 3840x2160 only)"] = ok
    checks["matcher: the formats' other frame rates and the 8K descriptors give the same answer, none is found at 3840x2560"] = (
        bool(untouched) and all(u["stock"] == u["changed"] and u["changed_3840x2560"] is None for u in untouched))
    res["encoder_selection"] = {"changed": sel, "untouched_checked": len(untouched), "untouched_examples": untouched[:6]}
    res["clip_code"] = [{"raster": [w, h], "stock": s.clip(w, h), "changed": c.clip(w, h)} for w, h in ((W1, H1), (W0, H0), (8192, 4320), (7680, 4320), (1920, 1080))]
    checks["clip-format code: 3840x2560 -> 23 (the 4K code) after the change, 0 before; 3840x2160 23, 7680x4320 4, 1920x1080 26 unchanged"] = (
        [x["changed"] for x in res["clip_code"]] == [23, 23, 0, 4, 26] and [x["stock"] for x in res["clip_code"]] == [0, 23, 3, 4, 26])
    # ---- the memory class: which ids the A1 II's memory function asks
    firsts = {}
    for q in design["descriptors"]:
        firsts.setdefault(s.desc(q["descriptor"])["codec"], q["descriptor"])
    mc = {hex(cd): {"descriptor": k, "request_3840x2560": {"stock": s.unit_ids(s.desc(k), W1, H1), "changed": c.unit_ids(s.desc(k), W1, H1)},
                    "request_3840x2160": {"stock": s.unit_ids(s.desc(k), W0, H0), "changed": c.unit_ids(s.desc(k), W0, H0)}} for cd, k in sorted(firsts.items())}
    res["memory_class_by_codec"] = mc
    checks["memory: a 3840x2560 request asks the 4K class's blocks after the change (0x486, 0x474, 0x47a, 0x477), 3840x2160 unchanged"] = all(
        v["request_3840x2560"]["changed"]["memory_ids_asked"][:4] == ["0x486", "0x474", "0x47a", "0x477"] and not v["request_3840x2560"]["changed"]["errors_logged"]
        and v["request_3840x2160"]["changed"] == v["request_3840x2160"]["stock"] for v in mc.values())
    checks["memory, stock: a 3840x2560 request would ask the 8K class's blocks without a CD (0x473, 0x479, 0x476: the A1 II skips CD id 0)"] = all(
        v["request_3840x2560"]["stock"]["memory_ids_asked"][:3] == ["0x473", "0x479", "0x476"] for v in mc.values())
    # the 8K consequence, for the record: an XAVC HS 8K request while applied asks the 4K class's blocks
    k8 = next(k for k in range(NDESC) if (s.desc(k)["w"], s.desc(k)["h"]) == (7680, 4320) and s.desc(k)["codec"] == 0xE and not s.desc(k)["infr"])
    d8 = s.desc(k8)
    res["xavc_hs_8k_while_applied"] = {"descriptor": k8, "stock": s.unit_ids(d8, 7680, 4320), "changed": c.unit_ids(d8, 7680, 4320)}
    # ---- DMM: the blocks asked together must be one layout of the main processor's DmmCfg
    groups = {}
    for i in ("0x486", "0x474", "0x47a", "0x477", "0x473", "0x479", "0x476"):
        groups[i] = sorted({(hex(u["group"]["gid"]), hex(u["group"]["parent"]), u["size"]) for u in id_units(cfg, int(i, 16))})
    res["dmm_layouts"] = groups
    g = lambda i: {x[0] for x in groups[i]}
    checks["DmmCfg: the four 4K blocks sit in one layout (group 0x83 of the 304.7 MB block 0x668, via 0x73a / 0x7d6); 8K ES 0x479 is that block's other layout"] = (
        g("0x474") == g("0x477") == {"0x83"} and g("0x486") == {"0x87"} and g("0x47a") == {"0x85"} and g("0x479") == {"0x82"})
    # ---- the codec's own memory calculation for the changed descriptors against row 3's blocks after the change
    fw = V.Firmware()
    table = [struct.unpack_from("<4I", changed, UNIT + 0x10 * k) for k in range(5)]
    have = [max((u["size"] for u in id_units(cfg, i)), default=None) if i else None for i in table[3]]
    mem = []
    for dd in V.descriptors(changed):
        if dd["index"] not in chg:
            continue
        need = fw.need(dd)
        t, _ = V.unit_type(dd)
        mem.append({"descriptor": dd["index"], "vsize": dd["h"], "unit_type": t, "need": {k: need[k] for k in ("cd", "ld", "multi")},
                    "fits": need["cd"] <= have[0] and need["ld"] <= have[1] and need["multi"] <= have[2], "firmware_asserts": need["asserts"]})
    res["codec_memory"] = {"blocks_of_row_3_after_the_change": {"ids": [hex(i) for i in table[3]], "bytes": have},
                           "largest_need": {k: max(m["need"][k] for m in mem) for k in ("cd", "ld", "multi")}, "rows": mem}
    checks["codec firmware: every changed descriptor's need at 3840x2560 fits the 4K blocks, unit type 3, no assert"] = bool(mem) and all(
        m["fits"] and m["unit_type"] == 3 and m["vsize"] == H1 and not m["firmware_asserts"] for m in mem)
    d8v = next(dd for dd in V.descriptors(av) if dd["index"] == k8)
    n8 = fw.need(d8v)
    res["xavc_hs_8k_while_applied"]["codec_need"] = {k: n8[k] for k in ("cd", "ld", "multi")}
    res["xavc_hs_8k_while_applied"]["fits_4k_blocks"] = n8["ld"] <= have[1] and n8["multi"] <= have[2]
    # ---- the start-block builder with each changed profile
    prof = {}
    for base, n in PROFILES:
        for k in range(n):
            prof[struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0]] = base + k * 0x100
    starts, good = [], True
    for p in design["descriptors"]:
        d = s.desc(p["descriptor"])
        o = prof[d["key"]]
        ten = d["bitl"] == 1
        try:
            a, seq_a = s.start_block(av[o:o + 0x100], d, W0, H0, ten)
            b, seq_b = c.start_block(changed[o:o + 0x100], d, W1, H1, ten)
        except RuntimeError as e:
            starts.append({"descriptor": p["descriptor"], "error": str(e)})
            good = False
            continue
        diff = [i for i in range(0x1C0) if seq_a[i] != seq_b[i]]
        runs = []
        for i in diff:
            if runs and i == runs[-1][1] + 1:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        starts.append({"descriptor": p["descriptor"], "key": d["key"], "stock_2160": a, "changed_2560": b,
                       "sequence_block_differs_at": [{"offset": hex(x), "bytes": y - x + 1, "stock": seq_a[x:y + 1].hex(), "changed": seq_b[x:y + 1].hex()} for x, y in runs]})
        good &= a["returned"] == 1 and not a["errors_logged"] and a["crop_size"] == [W0, H0]
        good &= b["returned"] == 1 and not b["errors_logged"] and b["crop_size"] == [W1, H1]
    res["start_block"] = {"rows": starts}
    checks["start block: every changed profile accepted, stock 3840x2160 and changed 3840x2560, no error logged"] = good
    return res, checks


def libmpr_checks(name, lm):
    design = json.loads((D / f"{name}.json").read_text(encoding="utf8"))
    changed = apply(lm, name, kind="libmpr")
    rows = {comb: {"stock": list(struct.unpack_from("<HH", lm, COMB + 0x18 * comb + 4)), "changed": list(struct.unpack_from("<HH", changed, COMB + 0x18 * comb + 4))}
            for comb in (0, 2, 4, 5, 7, 9, 12, 13)}
    libs = {"stock": emu_mp4_meta.Lib(lm, BUILD), "changed": emu_mp4_meta.Lib(changed, BUILD)}
    mp4 = {}
    for comb in (0, 2, 5, 7):
        for rate_code in (0, 2):
            got = {}
            for k, lib in libs.items():
                r, cfg = lib.config(comb, rate_code, 0x20)
                got[k] = [struct.unpack_from("<H", cfg, 0x2A)[0], struct.unpack_from("<H", cfg, 0x28)[0]]
            mp4[f"comb {comb} rate code {rate_code}"] = got
    want_h = H1 if any(p["kind"] == "L4-mp4size" for p in design["patches"]) else H0
    ok = (all(rows[c]["stock"] == [W0, H0] and rows[c]["changed"] == [W1, H1] for c in (0, 2, 5, 7))
          and all(rows[c]["stock"] == rows[c]["changed"] for c in (4, 9, 12, 13))
          and all(v["stock"] == [W0, H0] and v["changed"] == [W0, want_h] for v in mp4.values()))
    return {"encoder_request_raster_by_comb": {str(k): v for k, v in rows.items()}, "mp4_track_config_by_comb": mp4, "mp4_height_expected": want_h}, ok


def si_checks(av, lm, cfg):
    design = json.loads((D / f"{SI}.json").read_text(encoding="utf8"))
    s4 = json.loads((D / f"{STEP4}.json").read_text(encoding="utf8"))
    assert design["build"] == BUILD and design["artifact_sha256"]["av-cam.bin"] == s4["artifact_sha256"]["av-cam.bin"]
    res, checks = {"design": SI, "on_top_of": STEP4}, {}
    lms = {"stock": lm, "state": apply(lm, STEP4, kind="libmpr"), "state + S-I step": apply(lm, STEP4, SI, kind="libmpr"),
           "state v1 + S-I step": apply(lm, STEP4_V1, SI, kind="libmpr")}
    raster = lambda img, r: list(struct.unpack_from("<HH", img, COMB + 0x18 * r + 4))
    e = {k: {str(r): raster(v, r) for r in (0, 2, 5, 7, 9, 12)} for k, v in lms.items()}
    res["encoder_request"] = e
    checks["S-I: encoder request comb 9 3840x2160 -> 3840x2560 with the step; combs 0/2/5/7 as the state makes them; S-I DCI (12) untouched"] = (
        e["stock"]["9"] == [W0, H0] and e["state"]["9"] == [W0, H0] and e["state + S-I step"]["9"] == [W1, H1]
        and all(e["state + S-I step"][r] == e["state"][r] for r in ("0", "2", "5", "7", "12")) and e["state"]["12"] == [4096, 2160])
    libs = {k: emu_mp4_meta.Lib(v, BUILD) for k, v in lms.items()}
    mp4 = []
    for rate_code in (0, 2):
        for rate_index in range(2, 0x36):
            row = {"rate_code": rate_code, "rate_index": rate_index}
            for k, lib in libs.items():
                r, cfgb = lib.config(9, rate_code, rate_index)
                rs, sz = lib.stsd(cfgb)
                rp, pf = lib.prof(cfgb)
                row[k] = {"config": [struct.unpack_from("<H", cfgb, 0x2A)[0], struct.unpack_from("<H", cfgb, 0x28)[0]], "stsd": [rs, list(sz)], "prof": [rp, pf]}
            if row["stock"]["stsd"][0] == 0 and row["stock"]["prof"][0] == 0:
                mp4.append(row)
    checks["S-I: MP4 headers of an S-I file say 3840x2560 with the kit's v2 (stock profile id); 3840x2160 with v1"] = bool(mp4) and all(
        r["stock"]["config"] == [W0, H0] and r["state"] == r["state + S-I step"] and r["state"]["config"] == [W1, H1] and r["state"]["stsd"] == [0, [W1, H1]]
        and r["state"]["prof"][0] == 0 and r["state"]["prof"][1]["profile_id"] == r["stock"]["prof"][1]["profile_id"]
        and r["state v1 + S-I step"]["config"] == [W0, H0] for r in mp4)
    res["mp4_headers_comb_9"] = {"requests_the_stock_code_accepts": len(mp4), "example": mp4[0] if mp4 else None}
    stock, state, both = av, apply(av, STEP4), apply(av, STEP4, SI)
    s, t, c = Cam(stock), Cam(state), Cam(both)
    sel, good = [], True
    for p in design["descriptors"]:
        k = p["descriptor"]
        d = s.desc(k)
        row = {"descriptor": k, "rate": p["rate"], "class": p["quality_class"], "key": d["key"], "twin": p["twin_never_reached"],
               "stock_3840x2160": s.select(d, W0, H0), "state_3840x2560": t.select(d, W1, H1), "state_and_step_3840x2560": c.select(d, W1, H1),
               "state_and_step_3840x2160": c.select(d, W0, H0)}
        row["as_designed"] = (row["stock_3840x2160"] == k and row["state_3840x2560"] is None and row["state_and_step_3840x2560"] == k
                              and row["state_and_step_3840x2160"] == p["twin_never_reached"])
        good &= row["as_designed"]
        sel.append(row)
    checks["S-I: the A1 II's matcher finds each changed S-I descriptor for 3840x2560 (its 205xxx twin keeps 2160, never asked)"] = good
    chg = {p["descriptor"] for p in design["descriptors"]}
    twins = {p["twin_never_reached"] for p in design["descriptors"]}
    same, n, moved = True, 0, []
    for k in range(NDESC):
        d = s.desc(k)
        if k in chg or d["codec"] not in (4, 0xE, 0x18) or d["w"] < 1920:
            continue
        for w, h in ((d["w"], d["h"]), (W1, H1)):
            a, b = t.select(d, w, h), c.select(d, w, h)
            n += 1
            if a != b:
                moved.append({"built_from": k, "raster": [w, h], "state": a, "state_and_step": b})
                same &= (k in twins and (w, h) == (W0, H0) and a in chg and b == k) or ((w, h) == (W1, H1) and d["codec"] == 0x18 and a is None and b in chg)
    checks["S-I: every other AVC/HEVC/S-I request gives the same answer with and without the step (but a changed row's own match fields)"] = same
    checks["S-I: the HS/S step's own descriptors are still found at 3840x2560"] = all(c.select(s.desc(q["descriptor"]), W1, H1) == q["descriptor"] for q in s4["descriptors"])
    res["encoder_selection"] = {"changed": sel, "requests_compared": n, "answers_that_moved": moved}
    table = [struct.unpack_from("<4I", both, UNIT + 0x10 * k) for k in range(10)]
    d0 = s.desc(design["descriptors"][0]["descriptor"])
    ids0, ids1 = s.unit_ids(d0, W0, H0), c.unit_ids(d0, W1, H1)
    s_4k = next(q["descriptor"] for q in s4["descriptors"] if s.desc(q["descriptor"])["codec"] == 4 and q["rate"] == "23.98p")
    ids_s = s.unit_ids(s.desc(s_4k), W0, H0)
    res["memory_ids"] = {"stock_3840x2160": ids0, "state_and_step_3840x2560": ids1, "stock_xavc_s_4k_24p_3840x2160": ids_s}
    r4, r9 = table[4], table[9]
    checks["S-I: the memory function asks unit type 4's row (the 4K class's blocks) where stock asks type 9's; the blocks of a stock XAVC S 4K 24p recording"] = (
        r4 == (0x486, 0x474, 0x477, 0x47A) and r9 == (0x664, 0x474, 0x477, 0x690) and ids1["memory_ids_asked"][:4] == ids_s["memory_ids_asked"][:4]
        and ids1["memory_ids_asked"][0] == "0x486" and ids0["memory_ids_asked"][0] == "0x664" and not ids1["errors_logged"] and ids1["returned"] == ids0["returned"])
    fw = V.Firmware()
    size = {i: max(u["size"] for u in id_units(cfg, i)) for i in r4}
    mem, fit = [], True
    for dd in V.descriptors(both):
        if dd["index"] not in chg:
            continue
        need = fw.need(dd)
        f = (dd["w"], dd["h"]) == (W1, H1) and dd["use_core"] == 2 and need["cd"] <= size[r4[0]] and need["ld"] <= size[r4[1]] and need["multi"] <= size[r4[2]] and not need["asserts"]
        fit &= f
        mem.append({"descriptor": dd["index"], "raster": [dd["w"], dd["h"]], "need": {x: need[x] for x in ("cd", "ld", "multi")},
                    "have": {"cd": size[r4[0]], "ld": size[r4[1]], "multi": size[r4[2]]}, "fits": f})
    checks["S-I: the codec firmware's memory need for each changed descriptor fits unit type 4's blocks on the A1 II, no assert"] = fit
    res["codec_memory"] = mem
    prof = {}
    for base, cnt in PROFILES:
        for k in range(cnt):
            prof[struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0]] = base + k * 0x100
    starts, sgood = [], True
    for p in design["descriptors"]:
        d = s.desc(p["descriptor"])
        o = prof[d["key"]]
        a, seq_a = s.start_block(stock[o:o + 0x100], d, W0, H0, True)
        b, seq_b = c.start_block(both[o:o + 0x100], d, W1, H1, True)
        first0, first1 = struct.unpack_from("<H", seq_a, 0xC)[0], struct.unpack_from("<H", seq_b, 0xC)[0]
        ok = (a["returned"] == 1 and not a["errors_logged"] and a["crop_size"] == [W0, H0] and first0 == 1072
              and b["returned"] == 1 and not b["errors_logged"] and b["crop_size"] == [W1, H1] and first1 == 1280)
        sgood &= ok
        starts.append({"descriptor": p["descriptor"], "stock_3840x2160": a, "changed_3840x2560": b, "rows_for_first_core": [first0, first1], "ok": ok})
    checks["S-I: the start-block builder takes each profile: stock 3840x2160 (1072 rows first core), changed 3840x2560 (1280)"] = sgood
    res["start_block"] = starts
    res["clip_code"] = {"stock_3840x2160": s.clip(W0, H0), "stock_3840x2560": s.clip(W1, H1), "state_and_step_3840x2560": c.clip(W1, H1)}
    checks["S-I: clip-format code of 3840x2560 is the A1 II's 4K code 23 (from the HS/S step)"] = res["clip_code"]["state_and_step_3840x2560"] == CLIP_4K == res["clip_code"]["stock_3840x2160"]
    mine = [(p["binary"], int(p["file_off"], 16), len(p["new"]) // 2) for p in design["patches"]]
    theirs = []
    for nm in (STEP4, STEP4_V1):
        dj = json.loads((D / f"{nm}.json").read_text(encoding="utf8"))
        theirs += [(p["binary"], int(p["file_off"], 16), len(p["new"]) // 2) for p in dj["patches"]]
        theirs += [("libmpr.so", int(g["file_off"], 16), 4) for x in dj.get("libmpr_code_guards", []) for g in x["guards"]]
    checks["S-I: no site of the step is a site or guard of the HS/S step (v1, v2)"] = not any(a == b and x < y + m and y < x + n for a, x, n in mine for b, y, m in theirs)
    return res, checks


def main():
    a7 = locate_file.locate("a7iv_602", "av-cam.bin").read_bytes()
    av = locate_file.locate(BUILD, "av-cam.bin").read_bytes()
    lm = locate_file.locate(BUILD, "libmpr.so").read_bytes()
    cfg = dmm_cfg()
    out = {"about": "A1 II 4.00: function-level emulation of ogfile2560_hs_s_a1m2_v1 / _v2 and ogfilesi2560_a1m2_v1, stock against changed, on the A1 II's own "
                    "av-cam.bin and libmpr.so (build/run_ogfile_emu_a1m2.py). The requests are built from the descriptors' own fields, not from a traced "
                    "caller. Nothing was run on a camera.", "functions": find_functions(a7, av), "designs": [], "checks": {}}
    for name in HS_S:
        r, ck = hs_s_checks(name, av, cfg)
        r["libmpr"], ok = libmpr_checks(name, lm)
        ck["libmpr: comb rows 0/2/5/7 say 3840x2560 (4, 9, 12, 13 untouched); MP4 track height %s" % ("2560 (v2)" if name.endswith("v2") else "2160 (v1)")] = ok
        out["designs"].append(r)
        out["checks"].update({f"{name}: {k}": v for k, v in ck.items()})
    r, ck = si_checks(av, lm, cfg)
    out["designs"].append(r)
    out["checks"].update({f"{SI}: {k}": v for k, v in ck.items()})
    dst = ROOT / "evidence/a1m2/encoder/ogfile_emu_a1m2.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    bad = 0
    for text, ok in out["checks"].items():
        print("%s  %s" % ("PASS" if ok else "FAIL", text))
        bad += not ok
    v2 = out["designs"][1]
    print("memory ids, HS 3840x2560 after the change:", v2["memory_class_by_codec"]["0xe"]["request_3840x2560"]["changed"]["memory_ids_asked"],
          "| stock:", v2["memory_class_by_codec"]["0xe"]["request_3840x2560"]["stock"]["memory_ids_asked"])
    print("codec need, largest:", v2["codec_memory"]["largest_need"], "of", v2["codec_memory"]["blocks_of_row_3_after_the_change"])
    x8 = v2["xavc_hs_8k_while_applied"]
    print("XAVC HS 8K while applied: ids stock", x8["stock"]["memory_ids_asked"], "changed", x8["changed"]["memory_ids_asked"], "need", x8["codec_need"],
          "fits the 4K blocks:", x8["fits_4k_blocks"])
    print("S-I memory ids:", out["designs"][2]["memory_ids"]["state_and_step_3840x2560"]["memory_ids_asked"], "codec need e.g.", out["designs"][2]["codec_memory"][0]["need"])
    print("wrote", dst)
    print("ALL CHECKS PASS" if not bad else "%d CHECK(S) FAILED" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
