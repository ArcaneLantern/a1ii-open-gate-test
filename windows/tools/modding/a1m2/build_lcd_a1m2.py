"""A1 II 4.00 (a1m2_400) rear screen at 3:2 in open-gate movie mode with the focus frames: design lcdfill_a1m2_v1 (A1 II port, 2026-11-26).

  work\\venv\\Scripts\\python.exe -I -B build\\build_lcd_a1m2.py       writes modding/designs/lcdfill_a1m2_v1.json

The A7 IV's lcdfill_v2 (works on that camera: F791, F969) at the A1 II's addresses: the VDF fit word of a 16:9 picture on a panel of
code 1 (3:2) from 3 (letterbox) to 0 (fill), and the three frame widgets' expected rectangle for a 16:9 picture on the rear panel (row 1,
column 3 of their tables) from the stock letterbox (0, 38, 640, 404) to the whole panel (0, 0, 640, 480). Seven words, the change made in
coprocessor RAM only (levels 16/17 form, kind ram_words).

Facts asserted here against cpapp-b.bin 4.00 (loaded at 0x108000) and the A7 IV 6.02 / A7C II 2.01 images:
  - the fit-mode function and its tables (0x94 bytes) are the A7 IV's 0x1e4b78 byte for byte, once in the image, at 0x1fac50; the fit word
    of picture code 2 / panel code 1 is fn + 0x54 = 0x1faca4 (A7 IV 0x1e4bcc, A7C II 0x1f8f4c) and holds 3;
  - the three frame tables (0x78 bytes each: AF window, its remote-send variant, tracking frame) are the A7 IV's 0xd7b560 / 0xd7b5d8 /
    0xd7b650 byte for byte, at 0xf823c4 / 0xf8243c / 0xf824b4, found nowhere else; their entry +0x40 holds (0, 38, 640, 404);
  - the widgets build each table address with MOVW/MOVT at 0x128644 / 0x128e18 / 0x12993a (find_movw: the only references), and index the
    column through the table 0xd65140 = 2, 1, 0, 3, 0, 3, 0, 4 (the A7 IV's 0xb7c380, A7C II 0xccb8a0);
  - the rear panel's type byte is RAM 0x1a1c638 (0x705948: [0x1a1c61c + 0x1c], >= 4 -> 1), the EVF's 0x1a1c768 (0x70595a), and the type ->
    panel-code table 0xdc2778 is the FX2's 0xdc64dc (0, 2, 1, 0, ...: type 3 -> code 1 = 3:2, type 2 -> code 0 = 4:3).
NOT read on a camera: the rear panel type (expected 3: Sony gives the A1 II monitor as 3.2-type 2,095,104 dots = 1024 x 682 x 3, a 3:2
panel; appFw's feature table 0x33af000 gives 3:2 (value 2) or 4:3 (1) per product class, and which class the A1 II is was not established).
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402
import find_movw  # noqa: E402

B = 0x108000
CP = locate_file.locate("a1m2_400", "cpapp-b.bin").read_bytes()
CP4 = locate_file.locate("a7iv_602", "cpapp-b.bin").read_bytes()
CP2 = locate_file.locate("a7c2_201", "cpapp-b.bin").read_bytes()
FIT_FN, FIT = 0x1FAC50, 0x1FACA4
TABLES = (0xF823C4, 0xF8243C, 0xF824B4)
A7IV_TABLES = (0xD7B560, 0xD7B5D8, 0xD7B650)
WIDGET_LOADS = (0x128644, 0x128E18, 0x12993A)
COLUMN_MAP = 0xD65140
NAMES = ("cpActAfWindow (focus area frames), check 0x128530",
         "cpActAfWindowRemoteSend (the same frames for a remote viewer), check 0x128d50",
         "cpActTrackingFrame (tracking and face frames), check 0x1297d8")
STOCK, FILL = (0, 38, 640, 404), (0, 0, 640, 480)
u32 = lambda a: struct.unpack_from("<I", CP, a - B)[0]
raw = lambda a, n: CP[a - B:a - B + n]


def check():
    fn = raw(FIT_FN, 0x94)
    assert fn == CP4[0x1E4B78 - B:0x1E4B78 - B + 0x94] and CP.count(fn) == 1, "the fit-mode function is not the A7 IV's"
    assert FIT - FIT_FN == 0x1E4BCC - 0x1E4B78 and u32(FIT) == 3
    for t, t4 in zip(TABLES, A7IV_TABLES):
        assert raw(t, 0x78) == CP4[t4 - B:t4 - B + 0x78], hex(t)
        assert struct.unpack("<4H", raw(t + 0x40, 8)) == STOCK
    assert all(CP.count(raw(t, 0x78)) == 3 for t in TABLES), "the three tables are equal and nowhere else"
    loads = sorted(c for v, c, _ in find_movw.pairs(CP, TABLES[0], TABLES[2] + 0x78))
    assert loads == list(WIDGET_LOADS), loads
    assert struct.unpack("<8I", raw(COLUMN_MAP, 32)) == (2, 1, 0, 3, 0, 3, 0, 4)
    # the type byte -> panel code table, and the two type-byte getters (rear: >= 4 -> 1; EVF: >= 2 -> 2), as the FX2's 0x704ab8 / 0x704aca
    assert struct.unpack("<4I", raw(0xDC2778, 16)) == (0, 2, 1, 0) and CP2 is not None
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    for at, base, lim, ret in ((0x705948, 0x1A1C61C, 4, 1), (0x70595A, 0x1A1C74C, 2, 2)):
        ins = ["%s %s" % (i.mnemonic, i.op_str) for i in md.disasm(raw(at, 18), at)]
        assert ins[:7] == ["movw r0, #%#x" % (base & 0xFFFF), "movt r0, #%#x" % (base >> 16), "ldrb r0, [r0, #0x1c]", "cmp r0, #%d" % lim,
                           "it hs", "movhs r0, #%d" % ret, "bx lr"], ins
    return loads


def entry_words(rect):
    return struct.unpack("<2I", struct.pack("<4H", *rect))


def main():
    loads = check()
    sites = [{"ram_address": hex(FIT), "old": "03000000", "new": "00000000",
              "note": "VDF fit mode for a 16:9 picture on a 3:2 panel (table for picture code 2, entry for panel code 1): 3 letterbox to 0 fill. The rear "
                      "screen then shows the squeezed 16:9 live view over the whole 3:2 panel, i.e. stretched x32/27 vertically [A7 IV 0x1e4bcc, A7C II 0x1f8f4c]"}]
    guards = [{"ram_address": hex(FIT_FN), "bytes": raw(FIT_FN, 16).hex(), "note": "first 16 bytes of the fit-mode function, as in the file [A7 IV 0x1e4b78]"},
              {"ram_address": hex(FIT_FN + 0x40), "bytes": raw(FIT_FN + 0x40, 16).hex(), "note": "last 16 bytes of the fit-mode function before its tables, as in the file [A7 IV 0x1e4bb8]"},
              {"ram_address": hex(FIT - 4), "bytes": raw(FIT - 4, 4).hex(), "note": "picture code 2 (16:9), panel code 0 (4:3): 3 letterbox (the EVF's entry, left alone) [A7 IV 0x1e4bc8]"},
              {"ram_address": hex(FIT + 4), "bytes": raw(FIT + 4, 16).hex(), "note": "picture code 2, panel codes 2 to 5: 0, 0, 0, 2 [A7 IV 0x1e4bd0]"},
              {"ram_address": hex(FIT + 0x14), "bytes": raw(FIT + 0x14, 16).hex(), "note": "the table for picture code 1 (3:2), panel codes 0 to 3: 3, 0, 2, 0 [A7 IV 0x1e4be0]"}]
    assert struct.unpack("<4I", raw(FIT + 4, 16)) == (0, 0, 0, 2) and struct.unpack("<4I", raw(FIT + 0x14, 16)) == (3, 0, 2, 0) and u32(FIT - 4) == 3
    so, sn = entry_words(STOCK), entry_words(FILL)
    for t, t4, name in zip(TABLES, A7IV_TABLES, NAMES):
        e = t + 0x40
        for k, part in enumerate(("x, y", "w, h")):
            sites.append({"ram_address": hex(e + 4 * k), "old": struct.pack("<I", so[k]).hex(), "new": struct.pack("<I", sn[k]).hex(),
                          "note": "%s: expected live-view rectangle for a 16:9 picture on the rear panel, %s: stock letterbox (0, 38, 640, 404) to the whole panel "
                                  "(0, 0, 640, 480) [A7 IV %#x]" % (name, part, t4 + 0x40 + 4 * k)})
        assert struct.unpack("<4H", raw(e - 8, 8)) == (107, 0, 426, 480) and struct.unpack("<4H", raw(e + 8, 8)) == (0, 50, 640, 380)
        guards.append({"ram_address": hex(e - 8), "bytes": raw(e - 8, 8).hex(), "note": "the entry before (1:1 on the rear panel: 107, 0, 426, 480), as in the file [A7 IV %#x]" % (t4 + 0x38)})
        guards.append({"ram_address": hex(e + 8), "bytes": raw(e + 8, 8).hex(), "note": "the entry after (fifth aspect on the rear panel: 0, 50, 640, 380), as in the file [A7 IV %#x]" % (t4 + 0x48)})
    for s in sites:
        a = int(s["ram_address"], 16)
        assert raw(a, 4).hex() == s["old"] and a % 4 == 0
        assert not any(int(g["ram_address"], 16) < a + 4 and a < int(g["ram_address"], 16) + len(g["bytes"]) // 2 for g in guards)
    for g in guards:
        assert int(g["ram_address"], 16) % 4 == 0 and len(g["bytes"]) // 2 <= 16
    design = {"design": "lcdfill_a1m2_v1", "build": "a1m2_400",
              "title": "Rear screen (LCD) at 3:2 in movie mode with the focus frames: VDF fills the 3:2 panel with the 16:9 live view, and the frame widgets "
                       "expect the live view there (A1 II 4.00 port)",
              "kind": "ram_words",
              "artifact": "cpapp-b.bin, its loaded image in coprocessor RAM: the word is in the file, the change is made in RAM only",
              "artifact_sha256": hashlib.sha256(CP).hexdigest(),
              "generated_by": "build/build_lcd_a1m2.py",
              "ported_from": {"design": "lcdfill_v2", "build": "a7iv_602", "also": "lcdfill_c2_v2 (a7c2_201)"},
              "table": "VDF fit-mode table 0x1e4bc8 and the frame widgets' rectangle tables 0xd7b560, 0xd7b5d8, 0xd7b650 (entry: rear panel, 16:9) "
                       "[A7 IV addresses; A1 II: fit function 0x1fac50, fit table 0x1faca0, frame tables 0xf823c4, 0xf8243c, 0xf824b4]",
              "summary": {"sites": len(sites), "bytes": 4 * len(sites), "panel": "rear LCD, 3:2 (panel code 1)", "picture": "16:9 live view (picture code 2)",
                          "fit_stock": "letterbox (3)", "fit_new": "fill (0)", "frame_rectangle_stock": list(STOCK), "frame_rectangle_new": list(FILL),
                          "goes_with": ["the open-gate state (a 16:9 live view holding the whole 3:2 sensor area, squeezed 32/27)", "lcdcycle_a1m2_v1"]},
              "sites": sites, "guards": guards,
              "word_regions": {"FIT": ["0x1faca0", "0x1facb8"], "FRAMES": [[hex(t), hex(t + 0x78)] for t in TABLES],
                               "guard_only": [["0x1fac50", "0x1face4"]],
                               "note": "for a helper header in the gen_*_write.py WORD_REGIONS form: sites only inside FIT and FRAMES, guards also in the fit function"},
              "checked_against": ["cpapp-b.bin 4.00: fit function and tables byte-identical to the A7 IV's (0x1e4b78 -> 0x1fac50), frame tables byte-identical "
                                  "(0xd7b560 -> 0xf823c4), table loads %s, column map 0xd65140 = 2,1,0,3,0,3,0,4" % [hex(x) for x in loads],
                                  "emulated: build/emu_lcd_a1m2.py (the A1 II's own fit function, picture-ratio function 0x1faf70 and AF-window check 0x128530)",
                                  "NOT read on an A1 II: the rear panel type byte 0x1a1c638 (expected 3 = 3:2, panel code 1) and the EVF's 0x1a1c768"],
              "not_checked": ["on a camera: nothing of this design has run on an A1 II",
                              "the rear panel type (expected 3:2 by its 1024 x 682 dot count; a dump should read RAM 0x1a1c638)",
                              "that the open-gate live view of the A1 II port is a 16:9 frame (picture code 2) holding the whole 3:2 area, as on the A7 IV: "
                              "if the sensor-side design gives a native 3:2 live view instead, this step is not needed (3:2 on a 3:2 panel fills already)",
                              "the remote-send (0x128d50) and tracking (0x1297d8) checks were not emulated (same tables and edits; only 0x128530 was run)",
                              "with the camera's own De-Squeeze Display on, the layout uses its calculator 0x1fae78 instead of the picture-ratio function"]}
    out = ROOT / "modding/designs/lcdfill_a1m2_v1.json"
    out.write_text(json.dumps(design, indent=1) + "\n", encoding="utf8", newline="\n")
    print("lcdfill_a1m2_v1: %d sites, %d guards -> %s" % (len(sites), len(guards), out.relative_to(ROOT)))


if __name__ == "__main__":
    main()
