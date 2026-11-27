"""A1 II 4.00: run the resize set-up 0x521438 alone and show which first-scaler size it hands the second scaler (kit v2, 2026-11-26).

  C:\\Python313\\python.exe -B build\\emu_rcinput_a1m2.py [--save]

Why. The first A1 II run (tester, 2026-11-26; evidence/a1m2/tester_2026-11-26) applied ogsq_a1m2_v1 + outsz2560_a1m2_v1 + the encoder and
screen steps: every site TARGET, the sensor shadow held the full-height window, the live view showed the picture moved up with a purple/black
band at the bottom, and ~15 s later (or at record start) CAM_VD_SEQUENCE forced 'FW: S-Ele Refresh ng force exception' (0x509c76; view
struct 0x16237b0 in r4/r6/r8). On the FX2 the same ending came from its resize set-up's override (F1019). The A1 II's 0x521438 (called at
0x527074 with the view 0x16237b0) has its own form of that step:

  0x52175a  0x7cadca: the records' first-scaler size -> view +0x3c/+0x3e
  0x521748  sl = view byte +5 (set when request +0x1c != 0, +0x20 == 0, +0x88 != 1, +0x6c == 0: 0x5216ec..0x52170e)
  0x521778  if sl: 0xbceed4: W', H' = output (+0x40/+0x42) * 0x10000 / (0x10000 - margin), each capped at the crop (+0x38/+0x3a);
            stored into +0x3c/+0x3e only when the view's width is below W' (0x52177c..0x52178e)
  margin    0xbd22ce(ctx +0xe8, ctx byte +0x28, 0xbd2a9e(ctx +0x20)): 0 unless ctx +0xe8 is 1 or 3 and word 0x1951e58 is 0; then a u16 of
            the table 0x1951514 +0xa..+0x18 (RAM, filled at run time; SteadyShot's crop margin by its name in the FX2 trace)

What is run: the function itself on the A1 II's image, with RAM zero but for the movie size table (build/emu_size_table.py a1m2_400), the
request block the camera's path takes (P = ctx + 0x20: ctx +0xa40 set; drive mode 0x8c0; live; flag conditions met; size class 3), and the
margin table filled with one value per case (ctx +0xe8 = 3 so the margin is read). Sizes only: nothing here reaches hardware.
"""
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn import arm_const as A

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import emu_size_table  # noqa: E402
import locate_file  # noqa: E402

BUILD, B = "a1m2_400", 0x108000
IMG = locate_file.locate(BUILD, "cpapp-b.bin").read_bytes()
SETUP, RECORD_SIZE, OVERRIDE, PRINT = 0x521438, 0x7CADCA, 0xBCEED4, 0xBD9E8C
MARGIN_TABLE, MARGIN_OFF, MARGIN_RET = 0x1951514, 0x1951E58, 0xBCEEFC
H = 0x30000000                                      # harness block, outside the firmware's RAM
OBJ, OBJ2, CTX, VIEW, OUT, STACK, RET = H, H + 0x1000, H + 0x10000, H + 0x20000, H + 0x21000, H + 0x80000, H + 0x90000
DES = ROOT / "modding/designs"


def design_writes(name):
    d = json.loads((DES / f"{name}.json").read_text(encoding="utf8"))
    assert d["build"] == BUILD
    if d.get("kind") == "ram_words":
        return [(int(s["ram_address"], 16), bytes.fromhex(s["old"]), bytes.fromhex(s["new"])) for s in d["sites"]]
    return [(int(p["addr"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])) for p in d["patches"]]


def machine(designs, margin):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x100000, 0x2500000)
    uc.mem_map(H, 0x100000)
    uc.mem_write(B, IMG)
    t, rows, _ = emu_size_table.table(BUILD)
    assert t == 0x1938488 and (3840, 2160, 0x2D9) in rows, (hex(t), rows)
    uc.mem_write(t, b"".join(struct.pack("<HHI", *r) for r in rows))
    uc.mem_write(MARGIN_TABLE + 0xA, struct.pack("<8H", *([margin] * 8)))
    uc.mem_write(MARGIN_OFF, struct.pack("<I", 0))
    for name in designs:
        for addr, old, new in design_writes(name):
            assert bytes(uc.mem_read(addr, len(old))) == old, (name, hex(addr))
            uc.mem_write(addr, new)
    calls = {"print": 0, "override": 0, "margin_read": []}

    def hook(uc_, address, size, _):
        if address == MARGIN_RET:                    # 0xbceefc rsbs r2, r0, #0x10000: r0 = the margin 0xbd22ce returned
            calls["margin_read"].append(uc_.reg_read(A.UC_ARM_REG_R0))
        elif address == PRINT:                         # the firmware's log print: count it, return
            calls["print"] += 1
            uc_.reg_write(A.UC_ARM_REG_PC, uc_.reg_read(A.UC_ARM_REG_LR))
        elif address == OVERRIDE:
            calls["override"] += 1
    uc.hook_add(UC_HOOK_CODE, hook, begin=PRINT, end=PRINT)
    uc.hook_add(UC_HOOK_CODE, hook, begin=OVERRIDE, end=OVERRIDE)
    uc.hook_add(UC_HOOK_CODE, hook, begin=MARGIN_RET, end=MARGIN_RET)
    return uc, calls


def call(uc, addr, r0, r1=0, r2=0, r3=0, stack=()):
    sp = STACK - 0x100
    uc.mem_write(sp, b"".join(struct.pack("<I", x) for x in stack))
    for reg, v in ((A.UC_ARM_REG_R0, r0), (A.UC_ARM_REG_R1, r1), (A.UC_ARM_REG_R2, r2), (A.UC_ARM_REG_R3, r3),
                   (A.UC_ARM_REG_SP, sp), (A.UC_ARM_REG_LR, RET | 1)):
        uc.reg_write(reg, v)
    uc.emu_start(addr | 1, RET, count=400000)
    assert uc.reg_read(A.UC_ARM_REG_PC) == RET, hex(uc.reg_read(A.UC_ARM_REG_PC))


def run(designs, margin=0):
    uc, calls = machine(designs, margin)
    p = CTX + 0x20
    uc.mem_write(OBJ + 0xC, struct.pack("<I", CTX))
    uc.mem_write(OBJ + 0x38, struct.pack("<I", OBJ2))
    uc.mem_write(CTX + 0xA40, struct.pack("<I", 1))   # P = ctx + 0x20, view +1 = 0
    for off, v in ((0x00, 0x8C0),      # drive mode (view +0x44)
                   (0x18, 1),          # the request is live
                   (0x1C, 1),          # with +0x20 = 0, +0x88 != 1, +0x6c = 0: view bytes +4, +5 = 1 (0x5216ec..0x52170e)
                   (0x9C, 3),          # size class 3: base + 0xcc = 0x19384d0
                   (0xC8, 3)):         # ctx +0xe8 = 3: the margin function reads its table
        uc.mem_write(p + off, struct.pack("<I", v))
    call(uc, SETUP, OBJ, VIEW)
    view = bytes(uc.mem_read(VIEW, 0x54))
    call(uc, RECORD_SIZE, 0x8C0, 0, 0, 0, stack=(OUT, 0, 0))
    rec = struct.unpack("<HH", uc.mem_read(OUT, 4))
    u = lambda o: struct.unpack_from("<HH", view, o)
    return {"designs": list(designs), "margin": margin, "view": view.hex(), "flags_4_5": [view[4], view[5]], "first_stage": list(u(0x14)),
            "crop": list(u(0x38)), "first_scaler_in_view": list(u(0x3C)), "first_scaler_by_records": list(rec), "output": list(u(0x40)),
            "mode": hex(struct.unpack_from("<I", view, 0x44)[0]), "override_calls": calls["override"], "log_prints": calls["print"], "margin_read": calls["margin_read"],
            "sizes_agree": list(u(0x3C)) == list(rec)}


MARGINS = (0, 0x800, 0x1000, 0x1800, 0x2000, 0x3000)


def main():
    cases = {"stock": ((), 0), "ogsq": (("ogsq_a1m2_v1",), 0)}
    for m in MARGINS:
        cases["stock m=%#x" % m] = ((), m)
        cases["ogsq m=%#x" % m] = (("ogsq_a1m2_v1",), m)
        cases["ogsq+outsz m=%#x (the first run's state)" % m] = (("ogsq_a1m2_v1", "outsz2560_a1m2_v1"), m)
        cases["ogh2880+outsz m=%#x" % m] = (("ogh2880_a1m2_v1", "outsz2560_a1m2_v1"), m)
        cases["ogsq+outsz+fehold m=%#x" % m] = (("ogsq_a1m2_v1", "outsz2560_a1m2_v1", "fehold_a1m2_v1"), m)
    cases["stock+fehold"] = (("fehold_a1m2_v1",), 0)
    res = {k: run(*v) for k, v in cases.items()}
    for k, r in res.items():
        print("%-44s view %dx%d records %dx%d (%s); crop %dx%d; output %dx%d; flags %s; override %d; prints %d"
              % (k, *r["first_scaler_in_view"], *r["first_scaler_by_records"], "agree" if r["sizes_agree"] else "DIFFER", *r["crop"], *r["output"],
                 r["flags_4_5"], r["override_calls"], r["log_prints"]))
    checks = []

    def check(name, ok):
        checks.append((name, bool(ok)))
        print("  %s  %s" % ("PASS" if ok else "FAIL", name))
    check("stock: first scaler 4320x2430 in the view and by the records, output 3840x2160, at every margin",
          all(res["stock m=%#x" % m]["first_scaler_in_view"] == [4320, 2430] and res["stock m=%#x" % m]["sizes_agree"]
              and res["stock m=%#x" % m]["output"] == [3840, 2160] for m in MARGINS))
    check("the flag byte +5 is set on this path (the override is called)", res["stock"]["flags_4_5"] == [1, 1] and res["stock"]["override_calls"] == 1)
    check("ogh2880 + outsz: the records give 4320x2880 and the view agrees at every margin",
          all(res["ogh2880+outsz m=%#x" % m]["first_scaler_by_records"] == [4320, 2880] and res["ogh2880+outsz m=%#x" % m]["sizes_agree"] for m in MARGINS))
    check("ogsq + outsz + fehold: output 3840x2560, the view keeps the records' 4320x2430 at every margin, 0xbceed4 not called",
          all(res["ogsq+outsz+fehold m=%#x" % m]["output"] == [3840, 2560] and res["ogsq+outsz+fehold m=%#x" % m]["first_scaler_in_view"] == [4320, 2430]
              and res["ogsq+outsz+fehold m=%#x" % m]["override_calls"] == 0 for m in MARGINS))
    check("fehold alone leaves the stock view unchanged", res["stock+fehold"]["view"][2:] == res["stock"]["view"][2:]
          or res["stock+fehold"]["first_scaler_in_view"] == res["stock"]["first_scaler_in_view"])
    check("no case reaches a log print", all(r["log_prints"] == 0 for r in res.values()))
    check("the override reads the case's margin from the table (0xbd22ce -> 0xbceefc)",
          all(res["ogsq+outsz m=%#x (the first run's state)" % m]["margin_read"] == [m] for m in MARGINS))
    fires = {k: r for k, r in res.items() if k.startswith("ogsq+outsz m=") and not r["sizes_agree"]}
    verdict = {"first_run_state_differs_at": [res[k]["margin"] for k in fires], "crop_ogsq": res["ogsq"]["crop"], "crop_stock": res["stock"]["crop"],
               "first_run_state_views": {hex(r["margin"]): r["first_scaler_in_view"] for k, r in res.items() if k.startswith("ogsq+outsz m=")}}
    print("verdict:", json.dumps(verdict))
    ok = all(v for _, v in checks)
    print("%d of %d checks pass" % (sum(v for _, v in checks), len(checks)))
    if "--save" in sys.argv:
        out = {"about": "A1 II 4.00, 0x521438 (resize set-up) run alone: the first-scaler size the view hands on, against the size the mode's records "
                        "give, at margins 0..0x3000 of 0x10000 (build/emu_rcinput_a1m2.py). Sizes only; nothing here reaches hardware.",
               "verdict": verdict, "cases": res, "checks": [{"check": n, "pass": v} for n, v in checks]}
        (ROOT / "evidence/a1m2/rcinput_emu_a1m2.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
