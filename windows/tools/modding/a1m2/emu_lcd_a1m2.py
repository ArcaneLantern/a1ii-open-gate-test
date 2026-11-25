"""Emulate the A1 II 4.00 rear-screen layout pieces, stock and with lcdfill_a1m2_v1 applied, in Unicorn on the A1 II's own code.

  C:\\Python313\\python.exe -B build\\emu_lcd_a1m2.py [--save]          (--save writes evidence/a1m2/screen/lcdfill_a1m2_v1_emu.json)

Functions run (cpapp-b.bin 4.00, loaded at 0x108000), each called the way the layout 0x1fb074 calls it:
  0x1fac50  fit mode (panel code, picture aspect code)                                    (the A7 IV's 0x1e4b78, byte for byte)
  0x1faf70  picture ratio: (_, w | h << 16, panel code, aspect, [fit, flags, out])        -> out = x, y, w, h    (the A7S III / A7C II form)
  0x128530  frame check of cpActAfWindow (the focus frames). Not the A7 IV's code: it reads the output kind first (0x6a22f0: 2 -> selector 1,
            8 -> 2, else 0), then the live-view rectangle (0x69388e: y0, y1, x0, x1 and the output size; anything but 1 = accept), then for
            selector 0 the panel query 0x693b0e (0 -> row 0, 1 -> row 1, except an 800 x 600 output with 1, which is accepted at once);
            model aspect at +0x1e58 -> column through 0xd65140; 640 x 480 grid, tolerance 5 (as the A7 IV's)
Panels: 1024 x 682 and 720 x 480 (3:2: the A1 II's rear monitor is 1024 x 682 by its dot count; panel code 1, frame row 1) and 1024 x 768
(4:3: panel code 0, the EVF's kind of panel). Picture aspect 2 (16:9) is the open-gate live view. Every expected value is asserted.
Read-only apart from the evidence file.
"""
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn import arm_const as A

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402

B = 0x108000
IMG = locate_file.locate("a1m2_400", "cpapp-b.bin").read_bytes()
DESIGN = json.loads((ROOT / "modding/designs/lcdfill_a1m2_v1.json").read_text(encoding="utf8"))
RET, STK, OBJ = 0x2810000, 0x2700000, 0x2840000
FIT_FN, RATIO_FN, CHECK = 0x1FAC50, 0x1FAF70, 0x128530
PANELS = {"3:2 1024x682": (1024, 682, 1), "3:2 720x480": (720, 480, 1), "4:3 1024x768": (1024, 768, 0)}


class Cp:
    def __init__(self, patched):
        img = bytearray(IMG)
        if patched:
            for s in DESIGN["sites"]:
                a = int(s["ram_address"], 16)
                assert img[a - B:a - B + 4] == bytes.fromhex(s["old"])
                img[a - B:a - B + 4] = bytes.fromhex(s["new"])
            for g in DESIGN["guards"]:
                a = int(g["ram_address"], 16)
                assert img[a - B:a - B + len(g["bytes"]) // 2] == bytes.fromhex(g["bytes"])
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        try:
            uc.ctl_set_cpu_model(A.UC_CPU_ARM_CORTEX_A15)
        except Exception:
            pass
        uc.mem_map(0x100000, 0x2800000)                                  # the image, its RAM, and the harness's stack/objects up to 0x2900000
        uc.mem_write(B, bytes(img))
        uc.reg_write(A.UC_ARM_REG_C1_C0_2, uc.reg_read(A.UC_ARM_REG_C1_C0_2) | (0xF << 20))
        uc.reg_write(A.UC_ARM_REG_FPEXC, 0x40000000)
        self.stubs, self.log = {}, []
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, acc, addr, sz, v, _: self.log.append(f"unmapped {addr:#x} pc={u.reg_read(A.UC_ARM_REG_PC):#x}") or False)

    def stub(self, addr, fn):
        if addr not in self.stubs:
            self.uc.hook_add(UC_HOOK_CODE, lambda u, ad, sz, _: self._run_stub(ad), begin=addr, end=addr)
        self.stubs[addr] = fn

    def _run_stub(self, addr):
        u = self.uc
        r0 = self.stubs[addr](u)
        if r0 is not None:
            u.reg_write(A.UC_ARM_REG_R0, r0 & 0xFFFFFFFF)
        u.reg_write(A.UC_ARM_REG_PC, u.reg_read(A.UC_ARM_REG_LR))

    def call(self, fn, regs, stack=()):
        u = self.uc
        sp = STK - 0x800
        for i, v in enumerate(stack):
            u.mem_write(sp + 4 * i, struct.pack("<I", v & 0xFFFFFFFF))
        for r, v in zip((A.UC_ARM_REG_R0, A.UC_ARM_REG_R1, A.UC_ARM_REG_R2, A.UC_ARM_REG_R3), regs):
            u.reg_write(r, v & 0xFFFFFFFF)
        u.reg_write(A.UC_ARM_REG_SP, sp)
        u.reg_write(A.UC_ARM_REG_LR, RET | 1)
        u.emu_start(fn | 1, RET, count=200000)
        assert not self.log, self.log
        return u.reg_read(A.UC_ARM_REG_R0)

    def fit(self, panel, aspect):
        return self.call(FIT_FN, (panel, aspect))

    def ratio(self, w, h, panel, aspect):
        out = OBJ + 0x8000
        self.uc.mem_write(out, bytes(8))
        self.call(RATIO_FN, (0, w | h << 16, panel, aspect), (self.fit(panel, aspect), 0, out))
        return list(struct.unpack("<4H", bytes(self.uc.mem_read(out, 8))))

    def frame_check(self, live, out_w, out_h, kind=0, panel_q=1, model_aspect=4, lv_ok=1):
        m = OBJ + 0x10000
        u = self.uc
        u.mem_write(m, bytes(0x3000))
        u.mem_write(m + 0x1E58, struct.pack("<I", model_aspect))
        x, y, w, h = live

        def lv(uc):
            sp = uc.reg_read(A.UC_ARM_REG_SP)
            p_h = struct.unpack("<I", bytes(uc.mem_read(sp, 4)))[0]
            uc.mem_write(uc.reg_read(A.UC_ARM_REG_R1), struct.pack("<4i", y, y + h, x, x + w))
            uc.mem_write(uc.reg_read(A.UC_ARM_REG_R3), struct.pack("<H", out_w))
            uc.mem_write(p_h, struct.pack("<H", out_h))
            return lv_ok
        self.stub(0x6A22F0, lambda uc: kind)
        self.stub(0x69388E, lv)
        self.stub(0x693B0E, lambda uc: panel_q)
        return self.call(CHECK, (m,))


def run():
    st, pa = Cp(False), Cp(True)
    res = {"design": DESIGN["design"], "image_sha256": DESIGN["artifact_sha256"], "cases": []}
    case = lambda **k: res["cases"].append(k)
    # ---- fit mode of a 16:9 picture: letterbox stock; fill on the 3:2 panel patched; the 4:3 panel (EVF) unchanged; other codes unchanged
    for pc, want in ((1, (3, 0)), (0, (3, 3))):
        s, p = st.fit(pc, 2), pa.fit(pc, 2)
        assert (s, p) == want, (pc, s, p)
        case(what="fit mode, 16:9 picture", panel_code=pc, stock=s, patched=p)
    same = all(st.fit(pc, asp) == pa.fit(pc, asp) for pc in range(6) for asp in (0, 1, 3, 5)) and st.fit(2, 2) == pa.fit(2, 2) == 0
    assert same
    case(what="fit mode, every other panel/picture code pair", stock_equals_patched=True)
    # ---- the live view (de-squeeze off): the picture-ratio function with the fit word in force
    views = {}
    for name, (w, h, pc) in PANELS.items():
        s, p = st.ratio(w, h, pc, 2), pa.ratio(w, h, pc, 2)
        views[name] = (s, p)
        if pc == 1:
            assert p == [0, 0, w, h], (name, p)
            assert s[0] == 0 and s[2] == w and abs(s[3] - w * 9 / 16) <= 4 and abs(2 * s[1] + s[3] - h) <= 4, (name, s)
        else:
            assert s == p and s[2] == w and abs(s[3] - w * 9 / 16) <= 4, (name, s, p)
        for asp in (0, 1, 3, 5):
            assert st.ratio(w, h, pc, asp) == pa.ratio(w, h, pc, asp), (name, asp)
        case(what="live view, 16:9 picture (the open-gate frame)", panel=name, stock=s, patched=p, shown_aspect_patched=round(p[2] / p[3], 4),
             note="the whole 3:2 panel: the true shape of the 32/27-squeezed frame" if pc == 1 else "4:3 panel: letterbox kept (the EVF stays squeezed, as on the A7 IV)")
    # ---- the frame check (cpActAfWindow): rear output (kind 0), panel query 1 -> row 1
    for name in ("3:2 1024x682", "3:2 720x480"):
        w, h, _ = PANELS[name]
        s_live, p_live = views[name]
        r = {"stock_tables_stock_view": st.frame_check(s_live, w, h), "patched_tables_patched_view": pa.frame_check(p_live, w, h),
             "stock_tables_patched_view": st.frame_check(p_live, w, h), "patched_tables_stock_view": pa.frame_check(s_live, w, h)}
        assert r == {"stock_tables_stock_view": 1, "patched_tables_patched_view": 1, "stock_tables_patched_view": 0, "patched_tables_stock_view": 0}, (name, r)
        case(what="frame check 0x128530 (focus frames), rear output, row 1", panel=name, **r)
    # the C3 cycle's rectangles (lcdcycle_a1m2_v1): 2:1, 2.25:1, 2.4:1 letterboxes on the 1024 x 682 panel pass against the routine's entries
    # The picture of each state comes from the A1 II's own picture-ratio function with the routine's words written in (fit word 3 and the
    # constants `moveq.w lr, #n` / `it eq; moveq r0, #d` at 0x1fafa4 / 0x1fafa8, as lcdcycle_a1m2_v1 writes them).
    cyc = {}
    for label, words, entry, want_ratio in (("2:1", (0x0E01F04F, 0x2002BF08), (0, 60, 640, 360), 2.0),
                                            ("2.25:1", (0x0E04F04F, 0x2009BF08), (0, 80, 640, 320), 2.25),
                                            ("2.4:1", (0x0E05F04F, 0x200CBF08), (0, 90, 640, 300), 2.4)):
        for name in ("3:2 1024x682", "3:2 720x480"):
            w, h, pc = PANELS[name]
            tab = Cp(True)
            tab.uc.mem_write(0x1FACA4, struct.pack("<I", 3))
            tab.uc.mem_write(0x1FAFA4, struct.pack("<2I", *words))
            live = tab.ratio(w, h, pc, 2)
            for t in (0xF823C4, 0xF8243C, 0xF824B4):
                tab.uc.mem_write(t + 0x40, struct.pack("<4H", *entry))
            ok_ = tab.frame_check(live, w, h)
            cyc["%s on %s" % (label, name)] = {"live_view": live, "shown_ratio": round(live[2] / live[3], 4), "table_entry": list(entry), "accepted": ok_}
            assert ok_ == 1 and abs(live[2] / live[3] / want_ratio - 1) < 0.01 and live[0] == 0 and live[2] == w, (label, name, live)
    case(what="the C3 cycle's states: the A1 II's picture-ratio function with the routine's words gives each letterbox, and the frame check passes "
              "against the routine's table entries", results=cyc)
    # the 4:3 row (EVF kind of output) is untouched: a 16:9 letterbox on a 1024 x 768 output, panel query 0 -> row 0
    w4, h4, _ = PANELS["4:3 1024x768"]
    v4 = views["4:3 1024x768"][0]
    r4 = {"stock": st.frame_check(v4, w4, h4, panel_q=0), "patched": pa.frame_check(v4, w4, h4, panel_q=0)}
    assert r4 == {"stock": 1, "patched": 1}, r4
    case(what="frame check, 4:3 output (row 0: the letterbox, unchanged)", **r4)
    # an 800 x 600 output with the panel query 1 is accepted whatever the rectangle (the A1 II's own short cut)
    r8 = st.frame_check((0, 0, 1, 1), 800, 600)
    assert r8 == 1
    case(what="frame check, 800 x 600 output, panel query 1: accepted at once (A1 II code, not the A7 IV's)", result=r8)
    return res


if __name__ == "__main__":
    res = run()
    for c in res["cases"]:
        print(json.dumps(c))
    print(f"{len(res['cases'])} cases as expected")
    if "--save" in sys.argv:
        out = ROOT / "evidence" / "a1m2" / "screen" / "lcdfill_a1m2_v1_emu.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf8", newline="\n")
        print("wrote", out)
