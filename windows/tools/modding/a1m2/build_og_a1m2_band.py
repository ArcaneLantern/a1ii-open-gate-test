"""A1 II 4.00: diagnostic sensor design fhband_a1m2_v1 (the A7 IV's fhband_v1 idea): the sensor reads its full height, nothing else changes.

  C:\\Python313\\python.exe -B build\\build_og_a1m2_band.py

Why (first camera run, 2026-11-26, modding/A1M2_PORT.md section 6): with ogsq_a1m2_v1 applied the live view showed the lower part of each
frame empty and the camera core restarted ('S-Ele Refresh ng'). The resize override is ruled out by emulation (build/emu_rcinput_a1m2.py).
Left: (b) the sensor does not read beyond its 16:9 band in mode 0x14 although its window registers say full height, or (c) the first stage
or its raw buffer does not take the taller frame. This design separates the two: only the sensor's window registers (+ the read-out
table's mirror field [11] and read-out length [20]/[21], so the frame timing knows the read-out is longer) change; the receiver window, the
crop, the LC, the phase-detect stream, the geometry rows and both picture-record pairs stay stock, so the first stage keeps its stock 2,446
rows and takes the first lines the sensor sends.
  - If the sensor reads full height (window from block 1), those first lines are the TOP of the 3:2 frame: the picture is a normal 16:9
    picture whose framing is moved UP by about 225 binned rows (450 sensor rows, ~9% of the picture height): more above, less below.
  - If the sensor still reads its 16:9 band, the picture looks exactly like stock.
  - A restart here would say the extra lines themselves upset the receiver (neither of the above).
The four 4K modes' stored drive-parameter records are recomputed by the A1 II's own calculator with these cells (NTSC and PAL variants);
+4..+7 stay 2/1/2/1. Nothing here has run on an A1 II.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import build_og_a1m2 as G  # noqa: E402
import emu_drvparam as E  # noqa: E402

NAME = "fhband_a1m2_v1"


def main():
    idx, geo, mrows = G.check_sensor_facts()
    ro_len = 792
    sites, imgcells = [], []
    base, n = G.RO
    lo, hi = base + n * idx[0], base + n * (idx[-1] + 1)
    old = bytearray(G.rd(lo, hi - lo))
    new = bytearray(old)
    ed = {11: 63, 20: ro_len, 21: ro_len}
    for i in idx:
        for f, v in ed.items():
            struct.pack_into("<H", new, n * (i - idx[0]) + 2 * f, v)
            imgcells.append((base + n * i + 2 * f, v))
    sites.append({"kind": "S", "addr": hex(lo), "old": bytes(old).hex(), "new": bytes(new).hex(), "where": "file",
                  "note": f"read-out table {base:#x}, rows of indices 2-5 (0x820, 0x2820, 0x8c0, 0x28c0): "
                          + ", ".join(f"field {f} {G.u16(old, 2 * f)} -> {v}" for f, v in ed.items())})
    for off, (o, nv) in G.MATRIX_EDITS.items():
        a = G.MATRIX + G.MROW * mrows[off] + 4 + G.MCOL
        sites.append({"kind": "S", "addr": hex(a), "old": "%02x" % o, "new": "%02x" % nv, "where": "file",
                      "note": f"register matrix row {mrows[off]} (shadow +{off:#x}), column 2 (sensor mode 0x14, the four 4K modes only): {o} -> {nv}"})
        imgcells.append((a, bytes([nv])))
    sites.sort(key=lambda s: int(s["addr"], 16))
    f = E.CONSTS[G.BUILD]["fields"]
    pal = [(f[0x2C], G.rd(f[0x30], 24 * G.NMODES))]
    recs_out = {}
    stored = {}
    for system, bse in (("ntsc", []), ("pal", pal)):
        st, l1 = E.records(G.BUILD, bse)
        de, l2 = E.records(G.BUILD, bse + imgcells)
        assert not l1 and not l2 and all(st[m][2] is None and de[m][2] is None for m in st)
        changed = sorted(m for m in st if st[m][1] != de[m][1])
        assert changed == sorted(G.MODES), [hex(m) for m in changed]
        stored[system] = {m: (st[m][1], de[m][1]) for m in G.MODES}
    ids_all = G.ids()
    for m in G.MODES:
        var = {sy: stored[sy][m] for sy in ("ntsc", "pal")}
        for sy, (s, d) in var.items():
            assert s[4:8] == d[4:8] == b"\x02\x01\x02\x01"
            assert G.u16(d, 0x66) == 2430 and G.u16(d, 0x148) == ro_len and G.u16(s, 0x148) == 679, (hex(m), sy)
        offs = sorted({k for s, d in var.values() for k in range(len(s)) if s[k] != d[k]})
        recs_out[hex(m)] = {"index": ids_all.index(m), "offsets_that_differ": [hex(k) for k in offs],
                            **{sy: {"stock": var[sy][0].hex(), "design": var[sy][1].hex()} for sy in var}}
        print(f"stored record {m:#06x}: {len(offs)} bytes are sites {[hex(k) for k in offs]}")
    out = {"design": NAME, "build": G.BUILD, "camera": "ILCE-1M2 (A1 II), firmware 4.00",
           "title": "A1 II diagnostic: the sensor's window registers at full height (start block 1, half-height 30, +0x90 63) and the read-out "
                    "length, everything else stock (stock 2,446-row first stage): shows whether the sensor reads beyond its 16:9 band",
           "status": "built from the firmware files and emulated in parts; never run on a camera",
           "artifact": "cpapp-b.bin", "artifact_sha256": G.SHA, "generated_by": "build/build_og_a1m2_band.py",
           "ported_from": {"design": "fhband_v1", "build": "a7iv_602", "how": "full-height read-out with the stock first stage (F656-F658)"},
           "modes": [hex(m) for m in G.MODES], "mode_indices": idx,
           "summary": {"sites": len(sites), "bytes": sum(len(s["old"]) // 2 for s in sites),
                       "expected": {"sensor reads full height": "normal 16:9 picture, framing moved up ~9% of the picture height",
                                    "sensor keeps the 16:9 band": "picture exactly like stock",
                                    "restart": "the extra lines upset the receiver"}},
           "patches": sites, "record_size": 0x170,
           "stored_records": {k: {"index": v["index"], "offsets_that_differ": v["offsets_that_differ"],
                                  "ntsc": v["ntsc"], "pal": v["pal"]} for k, v in recs_out.items()},
           "stored_record_note": "RAM, filled by the camera at start-up from the tables; records base = the drive-parameter object's +0x10 "
                                 "(emulation " + hex(f[0x10]) + ") + index x 0x170",
           "stored_record_extra": []}
    dst = ROOT / "modding/designs" / f"{NAME}.json"
    dst.write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print(json.dumps(out["summary"]))
    print("wrote", dst)


if __name__ == "__main__":
    main()
